import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from laya import Router

from memoria import (
    MARGEN_DUDA, cargar as cargar_memoria, fusionar, incrustador, margen, memoria_activada, texto_issue, votar,
)
from modelos import leer_mezcla_base, leer_priores, rutas_modelos
from plantillas import cargar_plantillas, quitar_plantilla
from preguntas import PREGUNTAS_ISSUE, PREGUNTAS_PR
from repo import (
    NORMALIZADA_A_TIPO, contar_issues, etiquetas_del_repo, leer_pares, mapear_etiquetas, mezcla_desde_conteos,
    mezcla_manual, normalizar, pesos_para_ruta,
)

UMBRAL_TIPO = 0.60
UMBRAL_SPAM = 0.70
MAX_LINEAS_TRIVIAL = 5
MIN_CARACTERES_UTILES = 30
LIMITE_CUERPO = 1500
LIMITE_BACKLOG = 100
MAXIMO_BACKLOG = 500

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


def ajustar_con_memoria(router, repo, items, cuerpos, tipos):
    if not memoria_activada():
        return tipos, ["off"] * len(tipos)
    memoria = cargar_memoria(repo)
    if memoria is None:
        print("repo-memory está activado, pero todavía no hay memoria de este repo: corre el modo warm-cache")
        return tipos, ["missing"] * len(tipos)
    estados = ["not needed"] * len(tipos)
    dudosos = [i for i, tipo in enumerate(tipos) if margen(tipo["probabilities"]) <= MARGEN_DUDA]
    if not dudosos:
        return tipos, estados
    vectores = incrustador(router)([texto_issue(items[i]["title"], cuerpos[i]) for i in dudosos])
    nuevos = list(tipos)
    for i, vector in zip(dudosos, vectores):
        voto = votar(memoria, vector, items[i]["number"])
        if voto is None:
            estados[i] = "too few neighbors"
            continue
        nuevos[i], _ = fusionar(tipos[i], voto)
        estados[i] = "used"
    return nuevos, estados


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


def tipo_existente(item, nombres):
    propias = {nombre: tipo for tipo, nombre in nombres.items()}
    for etiqueta in item.get("labels") or []:
        nombre = etiqueta.get("name", "") if isinstance(etiqueta, dict) else str(etiqueta)
        tipo = propias.get(nombre) or NORMALIZADA_A_TIPO.get(normalizar(nombre))
        if tipo:
            return tipo, nombre
    return None, None


def spam_activado():
    return os.environ.get("LAYA_SPAM_CHECK", "false").strip().lower() == "true"


def en_modo_prueba():
    return os.environ.get("LAYA_DRY_RUN", "true").strip().lower() != "false"


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


def escribir_resumen(titulo, filas, modo_prueba):
    ruta = os.environ.get("GITHUB_STEP_SUMMARY")
    if not ruta:
        return
    estado = "Dry run: nothing was changed" if modo_prueba else "Changes applied"
    lineas = [
        f"### laya-triage · {titulo}",
        "",
        f"_{estado}_",
        "",
        "| Issue | Title | Decision | Confidence |",
        "|---|---|---|---|",
    ]
    for numero, texto, decision, confianza in filas:
        limpio = texto.replace("|", "\\|")[:80]
        porcentaje = f"{confianza:.0%}" if confianza is not None else "—"
        lineas.append(f"| #{numero} | {limpio} | {decision} | {porcentaje} |")
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas) + "\n\n")


def limite_backlog():
    try:
        limite = int(os.environ.get("LAYA_BACKLOG_LIMIT", LIMITE_BACKLOG))
    except ValueError:
        limite = LIMITE_BACKLOG
    return max(1, min(limite, MAXIMO_BACKLOG))


def issues_del_backlog(repo, nombres, limite):
    pendientes = []
    pagina = 1
    while len(pendientes) < limite:
        _, issues = llamar_api(
            "GET", f"/repos/{repo}/issues?state=open&sort=created&direction=desc&per_page=100&page={pagina}"
        )
        if not issues:
            break
        for issue in issues:
            if "pull_request" in issue:
                continue
            nombres_etiquetas = {e.get("name", "") for e in issue.get("labels") or []}
            if "needs-triage" in nombres_etiquetas or tipo_existente(issue, nombres)[0]:
                continue
            pendientes.append(issue)
            if len(pendientes) >= limite:
                break
        if len(issues) < 100:
            break
        pagina += 1
    return pendientes


def triar_backlog(evento, rutas, priores, bases):
    repo = evento.get("repository", {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        sys.exit("El modo backlog necesita GITHUB_REPOSITORY y GITHUB_TOKEN")

    nombres, mezcla = configuracion_del_repo(repo, token)
    limite = limite_backlog()
    issues = issues_del_backlog(repo, nombres, limite)
    print(f"{len(issues)} issues abiertos sin etiqueta de tipo en {repo} (límite {limite})")
    modo_prueba = en_modo_prueba()
    if not issues:
        escribir_resumen("backlog", [], modo_prueba)
        return

    lineas = cargar_plantillas(repo, token)
    cuerpos = [limpiar_cuerpo(quitar_plantilla(issue.get("body"), lineas)) for issue in issues]
    peticiones = [
        {"state": {"title": issue["title"], "body": cuerpo}, "questions": PREGUNTAS_ISSUE}
        for issue, cuerpo in zip(issues, cuerpos)
    ]
    router = Router(models=rutas, default="multilingual")
    resultados = router.predict_batch(peticiones, batch_size=8)

    tipos = []
    for resultado in resultados:
        modelo = resultado["routing"]["model"]
        pesos = pesos_para_ruta(mezcla, priores.get(modelo), bases.get(modelo))
        tipos.append(aplicar_priores(resultado["answers"]["tipo"], pesos))
    tipos, estados_memoria = ajustar_con_memoria(router, repo, issues, cuerpos, tipos)

    filas = []
    etiquetados = 0
    for issue, tipo, estado_memoria in zip(issues, tipos, estados_memoria):
        confianza = tipo["answer_confidence"]
        if confianza >= UMBRAL_TIPO:
            etiqueta = nombres[tipo["choice"]]
            decision = etiqueta + (" (repo memory)" if estado_memoria == "used" else "")
            etiquetados += 1
            if not modo_prueba:
                aplicar_cambios(repo, issue["number"], [etiqueta], None)
        else:
            decision = "left for a maintainer"
        filas.append((issue["number"], issue["title"], decision, confianza))
        print(f"#{issue['number']}: {decision} ({confianza:.0%}) · {issue['title'][:70]}")

    print(f"{etiquetados} de {len(issues)} issues con confianza suficiente")
    print("Modo dry-run: no se aplicó ningún cambio" if modo_prueba else "Etiquetas aplicadas")
    escribir_resumen(f"backlog · {etiquetados} of {len(issues)} labeled", filas, modo_prueba)


def main():
    evento = cargar_evento()
    modo = os.environ.get("LAYA_MODE", "triage").strip().lower()
    if "pull_request" in evento and modo != "backlog" and not spam_activado():
        print("La revisión de spam en pull requests está desactivada: usa spam-check: true para probarla")
        return

    rutas = rutas_modelos()
    priores = {nombre: leer_priores(carpeta) for nombre, carpeta in rutas.items()}
    bases = {nombre: leer_mezcla_base(carpeta) for nombre, carpeta in rutas.items()}

    if modo == "backlog":
        triar_backlog(evento, rutas, priores, bases)
        return

    estado_memoria = None
    if "pull_request" in evento:
        item = evento["pull_request"]
        cuerpo_util = limpiar_cuerpo(item.get("body"))
        lineas_plantilla = 0
        mezcla = None
        estado = {"title": item["title"], "body": cuerpo_util}
        router = Router(models=rutas, default="multilingual")
        resultado = router.predict(estado, PREGUNTAS_PR)
        etiquetas, comentario = decidir_pr(item, resultado["answers"])
        tipo_item = "pull_request"
    elif "issue" in evento:
        item = evento["issue"]
        cuerpo_util, lineas_plantilla = limpiar_issue(evento, item)
        repo = evento.get("repository", {}).get("full_name") or os.environ.get("GITHUB_REPOSITORY")
        nombres, mezcla = configuracion_del_repo(repo, os.environ.get("GITHUB_TOKEN"))
        tipo_previo, etiqueta_previa = tipo_existente(item, nombres)
        if tipo_previo:
            etiquetas, comentario = [], None
            if tipo_previo == "bug" and len(cuerpo_util) < MIN_CARACTERES_UTILES:
                etiquetas, comentario = ["needs-more-info"], COMENTARIO_INFO
            print(json.dumps({
                "tipo": "issue",
                "numero": item["number"],
                "titulo": item["title"],
                "ya_etiquetado": etiqueta_previa,
                "caracteres_utiles": len(cuerpo_util),
                "etiquetas": etiquetas,
                "comentario": comentario,
            }, indent=2, ensure_ascii=False))
            print(f"El issue ya tiene la etiqueta de tipo '{etiqueta_previa}': no lo vuelvo a clasificar")
            if etiquetas and not en_modo_prueba():
                aplicar_cambios(os.environ["GITHUB_REPOSITORY"], item["number"], etiquetas, comentario)
            return
        estado = {"title": item["title"], "body": cuerpo_util}
        router = Router(models=rutas, default="multilingual")
        resultado = router.predict(estado, PREGUNTAS_ISSUE)
        modelo = resultado["routing"]["model"]
        pesos = pesos_para_ruta(mezcla, priores.get(modelo), bases.get(modelo))
        tipo = aplicar_priores(resultado["answers"]["tipo"], pesos)
        tipos, estados_memoria = ajustar_con_memoria(router, repo, [item], [cuerpo_util], [tipo])
        resultado["answers"]["tipo"] = tipos[0]
        estado_memoria = estados_memoria[0]
        etiquetas, comentario = decidir_issue(resultado["answers"], cuerpo_util, nombres)
        tipo_item = "issue"
    else:
        sys.exit("Evento no soportado: solo issues y pull requests, o mode: backlog")

    resumen = {
        "tipo": tipo_item,
        "numero": item["number"],
        "titulo": item["title"],
        "modelo": resultado["routing"]["model"],
        "lineas_plantilla": lineas_plantilla,
        "mezcla_repo": {t: round(v, 3) for t, v in mezcla.items()} if mezcla else None,
        "memoria_repo": estado_memoria,
        "caracteres_utiles": len(cuerpo_util),
        "etiquetas": etiquetas,
        "comentario": comentario,
        "confianzas": {
            nombre: {"choice": r["choice"], "answer_confidence": round(r["answer_confidence"], 4)}
            for nombre, r in resultado["answers"].items()
        },
    }
    print(json.dumps(resumen, indent=2, ensure_ascii=False))

    modo_prueba = en_modo_prueba()
    confianza = resultado["answers"]["tipo"]["answer_confidence"] if tipo_item == "issue" else None
    decision = ", ".join(etiquetas) if etiquetas else "no changes"
    if estado_memoria == "used":
        decision += " (repo memory)"
    escribir_resumen(
        "new issue" if tipo_item == "issue" else "pull request",
        [(item["number"], item["title"], decision, confianza)],
        modo_prueba,
    )

    if not etiquetas and not comentario:
        print("No hay nada que aplicar")
        return

    if modo_prueba:
        print("Modo dry-run: no se aplicó ningún cambio")
        return

    repo = os.environ["GITHUB_REPOSITORY"]
    aplicar_cambios(repo, item["number"], etiquetas, comentario)
    print(f"Cambios aplicados en {repo}#{item['number']}")


if __name__ == "__main__":
    main()