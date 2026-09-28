import argparse

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entrenamiento_completo")
    parser.add_argument("--total", type=int, default=500000)
    parser.add_argument("--excluir", nargs="*", default=["datos/validacion.csv", "bench/muestra_test.csv"])
    parser.add_argument("--salida", default="datos/entrenamiento_natural.csv")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    datos = pd.read_csv(args.entrenamiento_completo, usecols=["id", "labels", "title", "body"]).fillna("")
    prohibidos = set()
    for ruta in args.excluir:
        prohibidos |= set(pd.read_csv(ruta, usecols=["id"])["id"])
    antes = len(datos)
    datos = datos[~datos["id"].isin(prohibidos)]
    print(f"{antes - len(datos)} issues descartados por estar en validación o test")

    elegidos = datos.sample(min(args.total, len(datos)), random_state=args.semilla)
    elegidos.to_csv(args.salida, index=False)
    print(f"{len(elegidos)} issues con la proporción natural guardados en {args.salida}")
    print((elegidos["labels"].value_counts(normalize=True) * 100).round(1).to_string())


if __name__ == "__main__":
    main()