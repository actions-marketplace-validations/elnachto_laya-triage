import argparse
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

TEMPORADAS = ["2024-10-01..2024-11-10", "2025-10-01..2025-11-10"]
CONSULTAS = {
    "spam": ['is:pr label:spam created:{fechas}', 'is:pr label:invalid created:{fechas}'],
    "genuino": ['is:pr is:merged label:hacktoberfest-accepted created:{fechas}'],
}
ESPERAS = [5, 15, 30]
ERRORES_RED = (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError)
LIMITE_PARCHE = 1500


def espera_por_limite(error):
    reinicio = error.headers.get("X-RateLimit-Reset") if error.headers else None
    if reinicio and reinicio.isdigit():
        return max(5, int(reinicio) - int(time.time()) + 2)
    return 60


def pedir(url, token):
    cabeceras = {"Accept": "application/vnd.github+json", "User-Agent": "laya-triage"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, headers=cabeceras)
    for intento, espera in enumerate([0] + ESPERAS):
        if espera:
            print(f"  Reintento {intento}/{len(ESPERAS)} en {espera} s")
            time.sleep(espera)
        try:
            with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                return json.load(respuesta)
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                pausa = espera_por_limite(error)
                print(f"  Límite de GitHub alcanzado: esperando {pausa} s")
                time.sleep(pausa)
                continue
            if error.code in (404, 410, 422, 451):
                return None
            print(f"  Error {error.code} en {url}")
        except ERRORES_RED as error:
            print(f"  Sin conexión: {type(error).__name__}")
    return None


def buscar(consulta, pagina, token):
    parametros = urllib.parse.urlencode({
        "q": consulta, "sort": "created", "order": "desc", "per_page": 100, "page": pagina,
    })
    respuesta = pedir(f"https://api.github.com/search/issues?{parametros}", token)
    return None if respuesta is None else respuesta.get("items", [])


def detalles(item, token):
    repo = item["repository_url"].split("/repos/")[-1]
    base = f"https://api.github.com/repos/{repo}/pulls/{item['number']}"
    pr = pedir(base, token)
    if not pr:
        return None
    archivos = pedir(f"{base}/files?per_page=30", token) or []
    parche = "\n".join(a.get("patch") or "" for a in archivos)[:LIMITE_PARCHE]
    return {
        "id": item["id"],
        "repo": repo,
        "numero": item["number"],
        "title": pr.get("title") or "",
        "body": pr.get("body") or "",
        "changed_files": pr.get("changed_files", 0),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "archivos": json.dumps([a.get("filename", "") for a in archivos], ensure_ascii=False),
        "parche": parche,
        "author_association": item.get("author_association", ""),
        "autor": (item.get("user") or {}).get("login", ""),
        "autor_bot": (item.get("user") or {}).get("type") == "Bot",
        "etiquetas": json.dumps([e["name"] for e in item.get("labels", [])], ensure_ascii=False),
        "created_at": item["created_at"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--por-clase", type=int, default=600)
    parser.add_argument("--max-por-repo", type=int, default=10)
    parser.add_argument("--paginas", type=int, default=10)
    parser.add_argument("--salida", default="datos/prs_hacktoberfest.csv")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Este script necesita GITHUB_TOKEN: hace más de 2000 peticiones")
    print("Usando GITHUB_TOKEN")

    candidatos = {"spam": {}, "genuino": {}}
    for clase, plantillas in CONSULTAS.items():
        for plantilla in plantillas:
            for fechas in TEMPORADAS:
                consulta = plantilla.format(fechas=fechas)
                print(f"Buscando {consulta}")
                for pagina in range(1, args.paginas + 1):
                    resultados = buscar(consulta, pagina, token)
                    time.sleep(2.2)
                    if not resultados:
                        break
                    for item in resultados:
                        if (item.get("user") or {}).get("type") == "Bot":
                            continue
                        candidatos[clase].setdefault(item["id"], item)
        print(f"  {len(candidatos[clase])} candidatos {clase}")

    ambiguos = candidatos["spam"].keys() & candidatos["genuino"].keys()
    for clase in candidatos:
        for clave in ambiguos:
            candidatos[clase].pop(clave, None)

    filas = []
    try:
        for clase, items in candidatos.items():
            por_repo = {}
            elegidos = 0
            for item in items.values():
                if elegidos >= args.por_clase:
                    break
                repo = item["repository_url"].split("/repos/")[-1]
                if por_repo.get(repo, 0) >= args.max_por_repo:
                    continue
                fila = detalles(item, token)
                time.sleep(0.3)
                if not fila:
                    continue
                fila["labels"] = clase
                filas.append(fila)
                por_repo[repo] = por_repo.get(repo, 0) + 1
                elegidos += 1
                if elegidos % 50 == 0:
                    print(f"  {clase}: {elegidos} con detalles")
    except KeyboardInterrupt:
        print("Interrumpido: guardo lo recolectado hasta ahora")

    if not filas:
        print("No se recolectó ningún PR. Revisa tu conexión a api.github.com")
        return
    datos = pd.DataFrame(filas).sample(frac=1, random_state=42)
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    datos.to_csv(args.salida, index=False)
    print(f"{len(datos)} PRs de {datos['repo'].nunique()} repos guardados en {args.salida}")
    print(datos["labels"].value_counts())
    print(datos.groupby("labels")[["changed_files", "additions", "deletions"]].median())


if __name__ == "__main__":
    main()