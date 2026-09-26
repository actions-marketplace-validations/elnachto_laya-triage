import sys

import pandas as pd


def main():
    origen = sys.argv[1]
    destino = sys.argv[2]
    cantidad = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

    datos = pd.read_csv(origen)
    muestra = datos.sample(n=cantidad, random_state=42)
    muestra.to_csv(destino, index=False)

    print(f"{len(muestra)} issues guardados en {destino}")
    print(muestra["labels"].value_counts())


if __name__ == "__main__":
    main()