import argparse
import gzip
import json

import pandas as pd

A_NUESTRAS = {"bug": "bug", "feature": "feature", "question": "question", "docs": "documentation"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entrada")
    parser.add_argument("--salida", default="datos/rival_test.csv")
    parser.add_argument("--excluir", nargs="*", default=["datos/entrenamiento_150k.csv", "datos/ml_entrenamiento.csv"])
    args = parser.parse_args()

    abrir = gzip.open if args.entrada.endswith(".gz") else open
    filas = []
    with abrir(args.entrada, "rt", encoding="utf-8") as archivo:
        for linea in archivo:
            fila = json.loads(linea)
            oro = json.loads(fila["gold"])
            if "issue_type" not in oro:
                continue
            estado = json.loads(fila["state"])
            filas.append({
                "id": fila["id"],
                "labels": A_NUESTRAS[oro["issue_type"]["label"]],
                "title": estado.get("title") or "",
                "body": estado.get("body") or "",
                "repo": fila.get("workflow", ""),
            })
    datos = pd.DataFrame(filas)
    normalizar = lambda texto: " ".join(str(texto).lower().split())
    vistos = set()
    for ruta in args.excluir:
        vistos |= set(pd.read_csv(ruta, usecols=["title"]).fillna("")["title"].map(normalizar))
    repetidos = datos["title"].map(normalizar).isin(vistos)
    print(f"{int(repetidos.sum())} de {len(datos)} issues ya estaban en nuestro entrenamiento: se descartan")
    datos = datos[~repetidos]
    datos.to_csv(args.salida, index=False)
    print(f"{len(datos)} issues guardados en {args.salida}")
    print(datos["labels"].value_counts().to_string())
    print(datos["repo"].value_counts().to_string())


if __name__ == "__main__":
    main()