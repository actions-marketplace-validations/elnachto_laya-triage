import argparse

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("test_completo")
    parser.add_argument("--excluir", nargs="*", default=["bench/muestra_test.csv"])
    parser.add_argument("--total", type=int, default=5000)
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--salida", default="datos/test_fresco.csv")
    args = parser.parse_args()

    datos = pd.read_csv(args.test_completo).fillna("")
    usados = set()
    for ruta in args.excluir:
        usados |= set(pd.read_csv(ruta, usecols=["id"])["id"])
    antes = len(datos)
    datos = datos[~datos["id"].isin(usados)]
    print(f"{antes - len(datos)} issues descartados por estar ya usados")

    elegidos = datos.sample(min(args.total, len(datos)), random_state=args.semilla)
    elegidos.to_csv(args.salida, index=False)
    print(f"{len(elegidos)} issues nuevos guardados en {args.salida}")
    print((elegidos["labels"].value_counts(normalize=True) * 100).round(1).to_string())


if __name__ == "__main__":
    main()
