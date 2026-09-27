import argparse
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

TIPOS = {
    "bug": ["bug"],
    "feature": ["enhancement", "feature"],
    "question": ["question"],
    "documentation": ["documentation", "docs"],
}
ETIQUETA_A_TIPO = {e: t for t, etiquetas in TIPOS.items() for e in etiquetas}
ESPERAS = [5, 15, 30]
ERRORES_RED = (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError)


def espera_por_limite(error):
    reinicio = error.headers.get("X-RateLimit-Reset") if error.headers else None
    if reinicio and reinicio.isdigit():
        return max(5, int(reinicio) - int(time.time()) + 2)
    return 60


def buscar(consulta, pagina, token):
    parametros = urllib.parse.urlencode({
        "q": consulta, "sort": "created", "order": "desc", "per_page": 100, "page": pagina,
    })
    cabeceras = {"Accept": "application/vnd.github+json", "User-Agent": "laya-triage"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(f"https://api.github.com/search/issues?{parametros}", headers=cabeceras)

    for intento, espera in enumerate([0] + ESPERAS):
        if espera:
            print(f"  Reintento {intento}/{len(ESPERAS)} de la página {pagina} en {espera} s")
            time.sleep(espera)
        try:
            with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                return json.load(respuesta).get("items", [])
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                pausa = espera_por_limite(error)
                print(f"  Límite de GitHub alcanzado: esperando {pausa} s")
                time.sleep(pausa)
                continue
            if error.code == 422:
                return []
            print(f"  Error {error.code} en la página {pagina}")
        except ERRORES_RED as error:
            print(f"  Sin conexión en la página {pagina}: {type(error).__name__}")
    print(f"  Página {pagina} omitida tras {len(ESPERAS)} reintentos")
    return None


def tipo_unico(issue):
    tipos = {ETIQUETA_A_TIPO[e["name"].lower()] for e in issue["labels"] if e["name"].lower() in ETIQUETA_A_TIPO}
    return tipos.pop() if len(tipos) == 1 else None


def guardar(filas, args):
    datos = pd.DataFrame(filas.values())
    datos = datos.sample(frac=1, random_state=42)
    datos = datos.groupby("repo", group_keys=False).head(args.max_por_repo)
    datos = pd.concat(
        grupo.head(args.por_clase) for _, grupo in datos.groupby("labels")
    ).sample(frac=1, random_state=42)
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    datos.to_csv(args.salida, index=False)
    print(f"{len(datos)} issues de {datos['repo'].nunique()} repos guardados en {args.salida}")
    print(datos["labels"].value_counts())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", default="2026-01-01")
    parser.add_argument("--por-clase", type=int, default=500)
    parser.add_argument("--max-por-repo", type=int, default=15)
    parser.add_argument("--paginas", type=int, default=10)
    parser.add_argument("--salida", default="datos/github_reciente.csv")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    pausa = 2.2 if token else 6.5
    print("Usando GITHUB_TOKEN" if token else "Sin GITHUB_TOKEN: la búsqueda irá más lenta")

    filas = {}
    fallos_seguidos = 0
    try:
        for tipo, etiquetas in TIPOS.items():
            for etiqueta in etiquetas:
                consulta = f'is:issue is:closed label:"{etiqueta}" created:>={args.desde}'
                print(f"Buscando {consulta}")
                for pagina in range(1, args.paginas + 1):
                    resultados = buscar(consulta, pagina, token)
                    time.sleep(pausa)
                    if resultados is None:
                        fallos_seguidos += 1
                        if fallos_seguidos >= 3:
                            print("  Tres páginas seguidas sin conexión: paso a la siguiente etiqueta")
                            fallos_seguidos = 0
                            break
                        continue
                    fallos_seguidos = 0
                    if not resultados:
                        break
                    for issue in resultados:
                        if tipo_unico(issue) != tipo or issue["id"] in filas:
                            continue
                        filas[issue["id"]] = {
                            "id": issue["id"],
                            "labels": tipo,
                            "title": issue["title"],
                            "body": issue.get("body") or "",
                            "author_association": issue.get("author_association", ""),
                            "repo": issue["repository_url"].split("/repos/")[-1],
                            "created_at": issue["created_at"],
                        }
                print(f"  Llevamos {len(filas)} issues")
    except KeyboardInterrupt:
        print("Interrumpido: guardo lo recolectado hasta ahora")

    if not filas:
        print("No se recolectó ningún issue. Revisa tu conexión a api.github.com")
        return
    guardar(filas, args)


if __name__ == "__main__":
    main()