import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from laya import Router

from modelos import leer_priores, rutas_modelos
from plantillas import cargar_plantillas, quitar_plantilla
from preguntas import PREGUNTAS_ISSUE, PREGUNTAS_PR
from repo import (
    contar_issues, etiquetas_del_repo, leer_pares, mapear_etiquetas, mezcla_desde_conteos, mezcla_manual,
    pesos_para_ruta,
)

UMBRAL_TIPO = 0.60
UMBRAL_SPAM = 0.70
MAX_LINEAS_TRIVIAL = 5
MIN_CARACTERES_UTILES = 30
LIMITE_CUERPO = 1500

PATRONES_RUIDO = [
    re.compile(r"^\s*#{1,6}\s"),
    re.compile(r"^\s*[-*]\s*\[[ xX]\]"),
    re.compile(r"^\s*(\d+\.|[-*])\s*$"),
    re.compile(r"^[^:]{1,60}:\s*$"),
    re.compile(r"^\s*_?no response_?\s*$", re.IGNORECASE),
]

ETIQUETAS_TIPO = {
    "bug": "bug",
    "feature": "enhancement",
    "question": "question",
    "docs": "documentation",
}

ESTILO_ETIQUETAS = {
    "bug": ("F2644B", "Something is not working"),
    "enhancement": ("2E9E68", "New feature or request"),
    "question": ("6B3FE7", "Further information is requested"),
    "documentation": ("16141F", "Improvements or additions to documentation"),
    "needs-triage": ("9C98AE", "Waiting for a maintainer to review"),
    "needs-more-info": ("6B3FE7", "Key details are missing from the report"),
    "spam-probable": ("9C98AE", "Looks like a low-effort change, review before merging"),
}

COMENTARIO_INFO = (
    "Thanks for opening this issue! It looks like some details are missing. "
    "Could you add the steps to reproduce, the version you are using and what you expected to happen?"
)

COMENTARIO_SPAM = (
    "This pull request looks like a very small change without a clear purpose. "
    "A maintainer will review it. If it is a real contribution, please describe what it fixes or improves."
)

FIRMA = (
    "\n\n---\n"
    "<sub>Automated triage by [laya-triage](https://github.com/elnachto/laya-triage). "
    "A maintainer will review this.</sub>"
)


def cargar_evento():
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_EVENT_PATH")
    if not ruta:
        sys.exit("No se encontró el evento: pasa una ruta o define GITHUB_EVENT_PATH")
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def limpiar_cuerpo(texto):
    sin_comentarios = re.sub(r"<!--.*?-->", "", texto or "", flags=re.DOTALL)
    lineas = []
    for linea in sin_comentarios.splitlines():
        if not linea.strip():
            continue
        if any(patron.search(linea) for patron in PATRONES_RUIDO):
            continue
        lineas.append(linea.strip())
    return "\n".join(lineas)[:LIMITE_CUERPO]


def limpiar_issue(evento, item):
    repo = evento.get("repository", {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY")
    lineas = cargar_plantillas(repo, os.environ.get("GITHUB_TOKEN")) if repo else set()
    sin_plantilla = quitar_plantilla(item.get("body"), lineas)
    return limpiar_cuerpo(sin_plantilla), len(lineas)


def aplicar_priores(respuesta, priores):
    if not priores:
        return respuesta
    pesos = {clase: p * priores.get(clase, 0.0) for clase, p in respuesta["probabilities"].items()}
    total = sum(pesos.values())
    if not total:
        return respuesta
    probabilidades = {clase: peso / total for clase, peso in pesos.items()}
    eleccion = max(probabilidades, key=probabilidades.get)
    return {**respuesta, "choice": eleccion, "answer_confidence": probabilidades[eleccion], "probabilities": probabilidades}


def configuracion_del_repo(repo, token):
    modo_etiquetas = os.environ.get("LAYA_LABELS", "auto").strip()
    modo_priores = os.environ.get("LAYA_CLASS_PRIORS", "auto").strip()
    existentes = etiquetas_del_repo(repo, token) if repo and token else []
    mapa = mapear_etiquetas(existentes)

    nombres = dict(ETIQUETAS_TIPO)
    if modo_etiquetas.lower() == "auto":
        nombres.update(mapa)
    else:
        nombres.update({t: n for t, n in leer_pares(modo_etiquetas).items() if t in ETIQUETAS_TIPO})

    mezcla = None
    if modo_priores.lower() == "auto":
        conteos = contar_issues(repo, token, mapa) if repo and token and mapa else None
        mezcla = mezcla_desde_conteos(conteos) if conteos else None
    elif modo_priores.lower() != "natural":
        mezcla = mezcla_manual(modo_priores)
    return nombres, mezcla


def spam_activado():
    return os.environ.get("LAYA_SPAM_CHECK", "false").strip().lower() == "true"


def decidir_issue(respuestas, cuerpo_util, nombres=None):
    etiquetas = []
    comentario = None
    nombres = nombres or ETIQUETAS_TIPO

    tipo = respuestas["tipo"]
    if tipo["answer_confidence"] >= UMBRAL_TIPO:
        etiquetas.append(nombres[tipo["choice"]])
    else:
        etiquetas.append("needs-triage")

    if tipo["choice"] == "bug" and len(cuerpo_util) < MIN_CARACTERES_UTILES:
        etiquetas.append("needs-more-info")
        comentario = COMENTARIO_INFO

    return etiquetas, comentario


def es_cambio_trivial(pr):
    lineas = pr.get("additions", 0) + pr.get("deletions", 0)
    return pr.get("changed_files", 0) <= 1 and lineas <= MAX_LINEAS_TRIVIAL


def decidir_pr(pr, respuestas):
    spam = respuestas["spam"]
    modelo_dice_spam = spam["choice"] == "B" and spam["answer_confidence"] >= UMBRAL_SPAM

    if modelo_dice_spam and es_cambio_trivial(pr):
        return ["spam-probable"], COMENTARIO_SPAM
    return [], None


def llamar_api(metodo, ruta, datos=None, codigos_aceptados=()):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Falta GITHUB_TOKEN para escribir en GitHub")

    cuerpo = json.dumps(datos).encode("utf-8") if datos is not None else None
    peticion = urllib.request.Request(
        f"https://api.github.com{ruta}",
        data=cuerpo,
        method=metodo,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "laya-triage",
        },
    )
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        if error.code in codigos_aceptados:
            return error.code, None
        detalle = error.read().decode("utf-8", errors="replace")
        sys.exit(f"Error {error.code} en {metodo} {ruta}: {detalle}")


def asegurar_etiqueta(repo, nombre):
    if nombre not in ESTILO_ETIQUETAS:
        return
    nombre_url = urllib.parse.quote(nombre, safe="")
    estado, _ = llamar_api("GET", f"/repos/{repo}/labels/{nombre_url}", codigos_aceptados=(404,))
    if estado != 404:
        return
    color, descripcion = ESTILO_ETIQUETAS[nombre]
    llamar_api(
        "POST",
        f"/repos/{repo}/labels",
        {"name": nombre, "color": color, "description": descripcion},
        codigos_aceptados=(422,),
    )


def aplicar_cambios(repo, numero, etiquetas, comentario):
    if etiquetas:
        for nombre in etiquetas:
            asegurar_etiqueta(repo, nombre)
        llamar_api("POST", f"/repos/{repo}/issues/{numero}/labels", {"labels": etiquetas})
    if comentario:
        llamar_api("POST", f"/repos/{repo}/issues/{numero}/comments", {"body": comentario + FIRMA})


def main():
    evento = cargar_evento()
    if "pull_request" in evento and not spam_activado():
        print("La revisión de spam en pull requests está desactivada: usa spam-check: true para probarla")
        return

    rutas = rutas_modelos()
    priores = {nombre: leer_priores(carpeta) for nombre, carpeta in rutas.items()}
    router = Router(models=rutas, default="multilingual")

    if "pull_request" in evento:
        item = evento["pull_request"]
        cuerpo_util = limpiar_cuerpo(item.get("body"))
        lineas_plantilla = 0
        mezcla = None
        estado = {"title": item["title"], "body": cuerpo_util}
        resultado = router.predict(estado, PREGUNTAS_PR)
        etiquetas, comentario = decidir_pr(item, resultado["answers"])
        tipo_item = "pull_request"
    elif "issue" in evento:
        item = evento["issue"]
        cuerpo_util, lineas_plantilla = limpiar_issue(evento, item)
        repo = evento.get("repository", {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY")
        nombres, mezcla = configuracion_del_repo(repo, os.environ.get("GITHUB_TOKEN"))
        estado = {"title": item["title"], "body": cuerpo_util}
        resultado = router.predict(estado, PREGUNTAS_ISSUE)
        modelo = resultado["routing"]["model"]
        pesos = pesos_para_ruta(mezcla, priores.get(modelo))
        resultado["answers"]["tipo"] = aplicar_priores(resultado["answers"]["tipo"], pesos)
        etiquetas, comentario = decidir_issue(resultado["answers"], cuerpo_util, nombres)
        tipo_item = "issue"
    else:
        sys.exit("Evento no soportado: solo issues y pull requests")

    resumen = {
        "tipo": tipo_item,
        "numero": item["number"],
        "titulo": item["title"],
        "modelo": resultado["routing"]["model"],
        "lineas_plantilla": lineas_plantilla,
        "mezcla_repo": {t: round(v, 3) for t, v in mezcla.items()} if mezcla else None,
        "caracteres_utiles": len(cuerpo_util),
        "etiquetas": etiquetas,
        "comentario": comentario,
        "confianzas": {
            nombre: {"choice": r["choice"], "answer_confidence": round(r["answer_confidence"], 4)}
            for nombre, r in resultado["answers"].items()
        },
    }
    print(json.dumps(resumen, indent=2, ensure_ascii=False))

    if not etiquetas and not comentario:
        print("No hay nada que aplicar")
        return

    modo_prueba = os.environ.get("LAYA_DRY_RUN", "true").strip().lower() != "false"
    if modo_prueba:
        print("Modo dry-run: no se aplicó ningún cambio")
        return

    repo = os.environ["GITHUB_REPOSITORY"]
    aplicar_cambios(repo, item["number"], etiquetas, comentario)
    print(f"Cambios aplicados en {repo}#{item['number']}")


if __name__ == "__main__":
    main()