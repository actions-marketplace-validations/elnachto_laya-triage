import argparse
import hashlib

import pandas as pd

COLUMNAS = ["id", "labels", "title", "body"]


def es_validacion(repo, porcentaje):
    return int(hashlib.sha1(f"validacion:{str(repo).lower()}".encode("utf-8")).hexdigest(), 16) % 100 < porcentaje


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recientes", default="datos/calidad/entrenamiento.csv")
    parser.add_argument("--repaso", default="D:/laya/datos/entrenamiento_1m.csv")
    parser.add_argument("--cantidad-repaso", type=int, default=50000)
    parser.add_argument("--porcentaje-validacion", type=int, default=5)
    parser.add_argument("--salida", default="datos/calidad/mezcla.csv")
    parser.add_argument("--salida-validacion", default="datos/calidad/validacion_reciente.csv")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    recientes = pd.read_csv(args.recientes).fillna("")
    en_validacion = recientes["repo"].map(lambda r: es_validacion(r, args.porcentaje_validacion))
    validacion = recientes[en_validacion]
    recientes = recientes[~en_validacion]
    print(f"Recientes: {len(recientes)} para entrenar y {len(validacion)} para validar "
          f"({validacion['repo'].nunique()} repos que el entrenamiento no ve)")

    repaso = pd.read_csv(args.repaso, usecols=COLUMNAS).fillna("")
    repaso = repaso.sample(min(args.cantidad_repaso, len(repaso)), random_state=args.semilla)
    print(f"Repaso de NLBSE: {len(repaso)} issues")

    mezcla = pd.concat([recientes[COLUMNAS], repaso[COLUMNAS]]).sample(frac=1, random_state=args.semilla)
    mezcla.to_csv(args.salida, index=False)
    validacion[COLUMNAS + ["repo"]].to_csv(args.salida_validacion, index=False)
    print(f"{len(mezcla)} issues guardados en {args.salida}")
    print((mezcla["labels"].value_counts(normalize=True) * 100).round(1).to_string())
    print(f"{len(validacion)} issues de validación guardados en {args.salida_validacion}")


if __name__ == "__main__":
    main()