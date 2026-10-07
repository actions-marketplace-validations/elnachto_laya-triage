import os
import sys
import urllib.parse

import numpy as np

from plantillas import cargar_plantillas, quitar_plantilla
from repo import NORMALIZADA_A_TIPO, consultar, etiquetas_del_repo, mapear_etiquetas, normalizar

CLASES = ["bug", "feature", "question", "docs"]
RUTA_MEMORIA = os.path.expanduser("~/.cache/laya-triage/memoria.npz")
POR_TIPO = 100
LARGO = 256
K_VECINOS = 20
MINIMO_VECINOS = 5
TEMPERATURA = 0.05
PESO = 0.4
MARGEN_DUDA = 0.4
SUAVIZADO = 0.02


def memoria_activada():
    return os.environ.get("LAYA_REPO_MEMORY", "false").strip().lower() == "true"


def texto_issue(titulo, cuerpo):
    return f"{titulo}\n\n{cuerpo}"[:4000]


def tipos_de_etiquetas(etiquetas):
    nombres = [e.get("name", "") if isinstance(e, dict) else str(e) for e in etiquetas or []]
    return {NORMALIZADA_A_TIPO.get(normalizar(n)) for n in nombres} - {None}


def issues_etiquetados(repo, token, mapa):
    vistos = {}
    for tipo, etiqueta in mapa.items():
        nombre = urllib.parse.quote(etiqueta, safe="")
        datos = consultar(
            f"/repos/{repo}/issues?labels={nombre}&state=closed&sort=created&direction=desc&per_page={POR_TIPO}", token
        )
        for issue in datos or []:
            if "pull_request" in issue or issue["number"] in vistos:
                continue
            if tipos_de_etiquetas(issue.get("labels")) != {tipo}:
                continue
            vistos[issue["number"]] = (tipo, issue.get("title") or "", issue.get("body") or "")
    return vistos


def incrustador(router):
    from laya import embed_fn_from_agent

    funcion = embed_fn_from_agent(router.load("english"), max_length=LARGO, batch_size=16)

    def incrustar(textos):
        vectores = np.asarray(funcion(textos), dtype=np.float32)
        return vectores / np.linalg.norm(vectores, axis=1, keepdims=True).clip(min=1e-9)

    return incrustar


def construir(repo, token, router, limpiar_cuerpo, ruta=RUTA_MEMORIA):
    mapa = mapear_etiquetas(etiquetas_del_repo(repo, token))
    if not mapa:
        print("El repo no tiene etiquetas de tipo reconocibles: no hay memoria que construir")
        return None
    issues = issues_etiquetados(repo, token, mapa)
    if len(issues) < MINIMO_VECINOS:
        print(f"Solo hay {len(issues)} issues cerrados con una etiqueta de tipo: no alcanza para la memoria")
        return None
    lineas = cargar_plantillas(repo, token)
    numeros = sorted(issues)
    textos = [texto_issue(issues[n][1], limpiar_cuerpo(quitar_plantilla(issues[n][2], lineas))) for n in numeros]
    vectores = incrustador(router)(textos)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    np.savez_compressed(
        ruta,
        vectores=vectores.astype(np.float16),
        tipos=np.array([CLASES.index(issues[n][0]) for n in numeros], dtype=np.int8),
        numeros=np.array(numeros, dtype=np.int64),
        repo=np.array(repo),
    )
    conteo = {t: sum(issues[n][0] == t for n in numeros) for t in CLASES}
    print(f"Memoria del repo guardada en {ruta}: {len(numeros)} issues {conteo}")
    return ruta


def cargar(repo, ruta=RUTA_MEMORIA):
    if not os.path.exists(ruta):
        return None
    datos = np.load(ruta)
    if str(datos["repo"]) != repo:
        return None
    return {
        "vectores": datos["vectores"].astype(np.float32),
        "tipos": datos["tipos"].astype(int),
        "numeros": datos["numeros"],
    }


def votar(memoria, vector, numero):
    pasados = memoria["numeros"] < numero
    if pasados.sum() < MINIMO_VECINOS:
        return None
    similitudes = memoria["vectores"][pasados] @ vector
    tipos = memoria["tipos"][pasados]
    orden = np.argsort(-similitudes)[:K_VECINOS]
    pesos = np.exp(similitudes[orden] / TEMPERATURA)
    conteo = np.zeros(len(CLASES))
    for tipo, peso in zip(tipos[orden], pesos):
        conteo[tipo] += peso
    conteo /= conteo.sum() or 1.0
    return {clase: float(valor) for clase, valor in zip(CLASES, conteo)}


def margen(probabilidades):
    valores = sorted(probabilidades.values(), reverse=True)
    return valores[0] - (valores[1] if len(valores) > 1 else 0.0)


def fusionar(respuesta, voto):
    probabilidades = respuesta["probabilities"]
    if voto is None or margen(probabilidades) > MARGEN_DUDA:
        return respuesta, False
    crudas = {c: probabilidades.get(c, 0.0) ** (1 - PESO) * (voto[c] + SUAVIZADO) ** PESO for c in CLASES}
    total = sum(crudas.values()) or 1.0
    nuevas = {c: v / total for c, v in crudas.items()}
    eleccion = max(nuevas, key=nuevas.get)
    return {**respuesta, "choice": eleccion, "answer_confidence": nuevas[eleccion], "probabilities": nuevas}, True


def main():
    from laya import Router

    from modelos import rutas_modelos
    from triage import limpiar_cuerpo

    os.makedirs(os.path.dirname(RUTA_MEMORIA), exist_ok=True)
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        sys.exit("Faltan GITHUB_REPOSITORY o GITHUB_TOKEN para construir la memoria")
    router = Router(models=rutas_modelos(), default="multilingual")
    construir(repo, token, router, limpiar_cuerpo)


if __name__ == "__main__":
    main()