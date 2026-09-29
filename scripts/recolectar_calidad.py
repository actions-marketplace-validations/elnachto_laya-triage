import argparse
import hashlib
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Lock

import pandas as pd

ETIQUETAS_TIPO = {
    "bug": ["bug", "type bug", "kind bug", "t bug", "bug report", "confirmed bug"],
    "feature": [
        "enhancement", "feature", "feature request", "new feature", "type feature",
        "type enhancement", "kind feature", "kind enhancement", "t feature", "t enhancement",
    ],
    "question": ["question", "type question", "kind question", "support", "type support", "t question"],
    "documentation": [
        "documentation", "docs", "doc", "type docs", "type documentation",
        "kind documentation", "kind docs", "area docs", "t docs",
    ],
}
ETIQUETAS_DESCARTE = {"invalid", "spam", "duplicate", "wontfix", "won t fix", "not planned", "stale"}
TRAMOS_ESTRELLAS = [
    "1000..1300", "1301..1700", "1701..2200", "2201..3000", "3001..4000",
    "4001..6000", "6001..9000", "9001..15000", "15001..30000", ">30000",
]
ESPERAS = [5, 15, 30, 60]
ERRORES_RED = (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError)

CONSULTA_REPOS = """
query($q: String!, $cursor: String) {
  rateLimit { remaining resetAt }
  search(query: $q, type: REPOSITORY, first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on Repository { nameWithOwner stargazerCount isArchived isFork hasIssuesEnabled } }
  }
}
"""

CONSULTA_ETIQUETAS = """
query($owner: String!, $name: String!) {
  rateLimit { remaining resetAt }
  repository(owner: $owner, name: $name) {
    labels(first: 100) { nodes { name } }
  }
}
"""

CONSULTA_ISSUES = """
query($owner: String!, $name: String!, $labels: [String!], $desde: DateTime!, $cursor: String, $tamano: Int!) {
  rateLimit { remaining resetAt }
  repository(owner: $owner, name: $name) {
    issues(first: $tamano, after: $cursor, states: CLOSED,
           filterBy: {labels: $labels, since: $desde},
           orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        databaseId number title body createdAt stateReason authorAssociation
        author { login __typename }
        labels(first: 20) { nodes { name } }
        timelineItems(itemTypes: [LABELED_EVENT], first: 20) {
          nodes { ... on LabeledEvent { label { name } actor { login __typename } } }
        }
      }
    }
  }
}
"""


def normalizar(nombre):
    texto = re.sub(r"[^a-z0-9]+", " ", nombre.lower()).strip()
    return texto


NORMALIZADA_A_TIPO = {normalizar(e): tipo for tipo, etiquetas in ETIQUETAS_TIPO.items() for e in etiquetas}


def tipo_de_etiqueta(nombre):
    return NORMALIZADA_A_TIPO.get(normalizar(nombre))


def parte_de_repo(repo, porcentaje_examen):
    cifra = int(hashlib.sha1(repo.lower().encode("utf-8")).hexdigest(), 16) % 100
    return "examen" if cifra < porcentaje_examen else "entrenamiento"


def consultar(consulta, variables, token, esperas=ESPERAS):
    cuerpo = json.dumps({"query": consulta, "variables": variables}).encode("utf-8")
    peticion = urllib.request.Request(
        "https://api.github.com/graphql",
        data=cuerpo,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "laya-triage", "Content-Type": "application/json"},
    )
    for intento, espera in enumerate([0] + esperas):
        if espera:
            print(f"    Reintento {intento}/{len(esperas)} en {espera} s")
            time.sleep(espera)
        try:
            with urllib.request.urlopen(peticion, timeout=60) as respuesta:
                datos = json.load(respuesta)
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                pausa = int(error.headers.get("Retry-After") or 60) if error.headers else 60
                print(f"    GitHub pide esperar: {pausa} s")
                time.sleep(pausa)
                continue
            if error.code in (401,):
                raise SystemExit("GITHUB_TOKEN inválido o vencido")
            print(f"    Error {error.code}")
            continue
        except ERRORES_RED as error:
            print(f"    Sin conexión: {type(error).__name__}")
            continue
        if datos.get("data") is None:
            print(f"    GitHub respondió con errores: {str(datos.get('errors'))[:200]}")
            continue
        limite = datos["data"].get("rateLimit") or {}
        if limite.get("remaining", 1000) < 100:
            reinicio = pd.Timestamp(limite["resetAt"]).timestamp()
            pausa = max(10, int(reinicio - time.time()) + 5)
            print(f"    Quedan {limite['remaining']} puntos de la API: espero {pausa} s")
            time.sleep(pausa)
        return datos["data"]
    return None


def buscar_repos(args, token):
    if os.path.exists(args.repos):
        with open(args.repos, encoding="utf-8") as archivo:
            repos = json.load(archivo)
        print(f"{len(repos)} repos leídos de {args.repos}")
        return repos
    repos = {}
    for tramo in TRAMOS_ESTRELLAS:
        consulta = f"stars:{tramo} archived:false fork:false pushed:>={args.activo_desde} sort:stars"
        print(f"Buscando repos {consulta}")
        cursor = None
        while True:
            datos = consultar(CONSULTA_REPOS, {"q": consulta, "cursor": cursor}, token)
            if not datos:
                break
            busqueda = datos["search"]
            for nodo in busqueda["nodes"]:
                if nodo and nodo.get("hasIssuesEnabled") and not nodo.get("isArchived") and not nodo.get("isFork"):
                    repos[nodo["nameWithOwner"]] = nodo["stargazerCount"]
            if not busqueda["pageInfo"]["hasNextPage"]:
                break
            cursor = busqueda["pageInfo"]["endCursor"]
            time.sleep(args.pausa)
        print(f"  Llevamos {len(repos)} repos")
    lista = sorted(repos, key=repos.get, reverse=True)
    os.makedirs(os.path.dirname(args.repos) or ".", exist_ok=True)
    with open(args.repos, "w", encoding="utf-8") as archivo:
        json.dump(lista, archivo, indent=0)
    print(f"{len(lista)} repos guardados en {args.repos}")
    return lista


def etiquetas_de_tipo(repo, token):
    dueno, nombre = repo.split("/", 1)
    datos = consultar(CONSULTA_ETIQUETAS, {"owner": dueno, "name": nombre}, token)
    if not datos or not datos.get("repository"):
        return {}
    return {e["name"]: tipo_de_etiqueta(e["name"]) for e in datos["repository"]["labels"]["nodes"] if tipo_de_etiqueta(e["name"])}


def quien_etiqueto(issue, etiqueta):
    for evento in issue["timelineItems"]["nodes"]:
        if evento and evento.get("label") and evento["label"]["name"] == etiqueta:
            return evento.get("actor") or {}
    return None


def evaluar_issue(issue, tipos_repo, args):
    if not issue or not issue.get("databaseId"):
        return None, "vacío"
    if issue["createdAt"][:10] < args.desde:
        return None, "antiguo"
    autor = issue.get("author") or {}
    if autor.get("__typename") == "Bot" or autor.get("login", "").endswith("[bot]"):
        return None, "bot"
    nombres = [e["name"] for e in issue["labels"]["nodes"]]
    if any(normalizar(n) in ETIQUETAS_DESCARTE for n in nombres):
        return None, "descartado"
    tipos = {tipos_repo[n] for n in nombres if n in tipos_repo}
    if len(tipos) != 1:
        return None, "ambiguo"
    tipo = tipos.pop()
    etiqueta = next(n for n in nombres if tipos_repo.get(n) == tipo)
    actor = quien_etiqueto(issue, etiqueta)
    if actor is None:
        return None, "sin_historial"
    if actor.get("__typename") == "Bot" or actor.get("login", "").endswith("[bot]"):
        return None, "etiqueta_de_bot"
    if actor.get("login") and actor.get("login") == autor.get("login"):
        return None, "etiqueta_del_autor"
    cuerpo = issue.get("body") or ""
    if len(re.sub(r"\s+", " ", cuerpo).strip()) < args.min_caracteres:
        return None, "cuerpo_corto"
    return {
        "id": issue["databaseId"],
        "labels": tipo,
        "title": issue["title"],
        "body": cuerpo,
        "repo": None,
        "numero": issue["number"],
        "created_at": issue["createdAt"],
        "state_reason": issue.get("stateReason") or "",
        "author_association": issue.get("authorAssociation") or "",
        "etiqueta_original": etiqueta,
        "etiquetado_por": actor.get("login", ""),
    }, "ok"


def issues_de_repo(repo, tipos_repo, args, token, motivos):
    dueno, nombre = repo.split("/", 1)
    elegidos = []
    cursor = None
    tamanos = [25, 10, 5]
    nivel = 0
    paginas = 0
    while len(elegidos) < args.max_por_repo and paginas < args.max_paginas:
        datos = consultar(
            CONSULTA_ISSUES,
            {"owner": dueno, "name": nombre, "labels": list(tipos_repo), "desde": f"{args.desde}T00:00:00Z",
             "cursor": cursor, "tamano": tamanos[nivel]},
            token,
            esperas=[3],
        )
        if not datos or not datos.get("repository"):
            nivel += 1
            if nivel >= len(tamanos):
                print(f"    {repo}: GitHub no logra responder, sigo con el siguiente repo")
                break
            print(f"    Pido páginas más chicas ({tamanos[nivel]} issues)")
            continue
        pagina = datos["repository"]["issues"]
        paginas += 1
        antiguos = 0
        for issue in pagina["nodes"]:
            fila, motivo = evaluar_issue(issue, tipos_repo, args)
            with CANDADO:
                motivos[motivo] = motivos.get(motivo, 0) + 1
            if motivo == "antiguo":
                antiguos += 1
            if fila:
                fila["repo"] = repo
                elegidos.append(fila)
        if antiguos == len(pagina["nodes"]) or not pagina["pageInfo"]["hasNextPage"]:
            break
        cursor = pagina["pageInfo"]["endCursor"]
        time.sleep(args.pausa)
    return elegidos[:args.max_por_repo]


CANDADO = Lock()


def procesar_repo(repo, args, token, motivos):
    tipos_repo = etiquetas_de_tipo(repo, token)
    return repo, (issues_de_repo(repo, tipos_repo, args, token, motivos) if tipos_repo else [])


def leer_avance(ruta):
    filas, hechos = [], set()
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as archivo:
            for linea in archivo:
                registro = json.loads(linea)
                hechos.add(registro["repo"])
                filas.extend(registro["issues"])
    return filas, hechos


def repos_excluidos(rutas):
    excluidos = set()
    for ruta in rutas:
        if os.path.exists(ruta):
            excluidos |= {r.lower() for r in pd.read_csv(ruta, usecols=["repo"])["repo"].dropna()}
    return excluidos


def guardar(filas, salida):
    datos = pd.DataFrame(filas).drop_duplicates("id").sample(frac=1, random_state=42)
    datos.to_csv(salida, index=False)
    print(f"\n{len(datos)} issues de {datos['repo'].nunique()} repos guardados en {salida}")
    print((datos["labels"].value_counts(normalize=True) * 100).round(1).to_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parte", choices=["entrenamiento", "examen"], required=True)
    parser.add_argument("--meta", type=int, required=True)
    parser.add_argument("--porcentaje-examen", type=int, default=35)
    parser.add_argument("--desde", default="2025-01-01")
    parser.add_argument("--activo-desde", default="2026-06-01")
    parser.add_argument("--max-por-repo", type=int, default=200)
    parser.add_argument("--min-caracteres", type=int, default=30)
    parser.add_argument("--pausa", type=float, default=0.5)
    parser.add_argument("--hilos", type=int, default=4)
    parser.add_argument("--max-paginas", type=int, default=20)
    parser.add_argument("--repos", default="datos/calidad/repos.json")
    parser.add_argument("--excluir", nargs="*", default=["datos/github_reciente.csv"])
    parser.add_argument("--salida", default="")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Falta GITHUB_TOKEN: ponlo en la terminal con set GITHUB_TOKEN=...")
    salida = args.salida or f"datos/calidad/{args.parte}.csv"
    avance = salida.replace(".csv", "_avance.jsonl")
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)

    repos = buscar_repos(args, token)
    excluidos = repos_excluidos(args.excluir)
    candidatos = [r for r in repos if parte_de_repo(r, args.porcentaje_examen) == args.parte and r.lower() not in excluidos]
    filas, hechos = leer_avance(avance)
    print(f"Parte {args.parte}: {len(candidatos)} repos candidatos, {len(hechos)} ya revisados, {len(filas)} issues guardados")

    motivos = {}
    pendientes = iter([r for r in candidatos if r not in hechos])
    revisados = len(hechos)
    en_curso = set()
    grupo = ThreadPoolExecutor(max_workers=args.hilos)

    def lanzar():
        while len(en_curso) < args.hilos * 2:
            repo = next(pendientes, None)
            if repo is None:
                return
            en_curso.add(grupo.submit(procesar_repo, repo, args, token, motivos))

    try:
        with open(avance, "a", encoding="utf-8") as archivo:
            lanzar()
            while en_curso and len(filas) < args.meta:
                listos, _ = wait(en_curso, return_when=FIRST_COMPLETED)
                for futuro in listos:
                    en_curso.discard(futuro)
                    try:
                        repo, nuevos = futuro.result()
                    except Exception as error:
                        print(f"    Falló un repo: {type(error).__name__}: {error}")
                        continue
                    filas.extend(nuevos)
                    revisados += 1
                    archivo.write(json.dumps({"repo": repo, "issues": nuevos}, ensure_ascii=False) + "\n")
                    archivo.flush()
                    print(f"[{revisados}/{len(candidatos)}] {repo}: +{len(nuevos)} · total {len(filas)}/{args.meta}")
                    if revisados % 25 == 0:
                        with CANDADO:
                            print(f"  Motivos de descarte hasta ahora: {dict(motivos)}")
                if len(filas) < args.meta:
                    lanzar()
    except KeyboardInterrupt:
        print("Interrumpido: guardo lo recolectado. Si vuelves a correr el mismo comando, sigue donde quedó")
    finally:
        grupo.shutdown(wait=False, cancel_futures=True)

    if not filas:
        print("No se recolectó ningún issue")
        return
    guardar(filas, salida)
    print(f"Motivos de descarte: {motivos}")


if __name__ == "__main__":
    main()
