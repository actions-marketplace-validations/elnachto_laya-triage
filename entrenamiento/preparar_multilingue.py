import argparse
import glob
import os

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traducciones", default="datos/traducciones/entrenamiento")
    parser.add_argument("--ingles", default="datos/entrenamiento.csv")
    parser.add_argument("--ingles-por-clase", type=int, default=2500)
    parser.add_argument("--fraccion-validacion", type=float, default=0.1)
    parser.add_argument("--salida-entrenamiento", default="datos/ml_entrenamiento.csv")
    parser.add_argument("--salida-validacion", default="datos/ml_validacion.csv")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    traducidos = pd.concat(
        pd.read_csv(ruta).fillna("") for ruta in sorted(glob.glob(os.path.join(args.traducciones, "*.csv")))
    )
    ids = np.array(sorted(traducidos["id"].unique()))
    generador = np.random.default_rng(args.semilla)
    ids_validacion = set(generador.choice(ids, size=int(len(ids) * args.fraccion_validacion), replace=False))
    en_validacion = traducidos["id"].isin(ids_validacion)

    ingles = pd.read_csv(args.ingles).fillna("")
    ingles = ingles[~ingles["id"].isin(set(ids))]
    extra = pd.concat(
        grupo.sample(min(args.ingles_por_clase, len(grupo)), random_state=args.semilla)
        for _, grupo in ingles.groupby("labels")
    ).assign(idioma="en")[["id", "labels", "title", "body", "idioma"]]

    entrenamiento = pd.concat([traducidos[~en_validacion], extra]).sample(frac=1, random_state=args.semilla)
    validacion = traducidos[en_validacion].sample(frac=1, random_state=args.semilla)

    entrenamiento.to_csv(args.salida_entrenamiento, index=False)
    validacion.to_csv(args.salida_validacion, index=False)
    print(f"Entrenamiento: {len(entrenamiento)} filas -> {args.salida_entrenamiento}")
    print(entrenamiento["idioma"].value_counts().to_string())
    print(entrenamiento["labels"].value_counts().to_string())
    print(f"Validación: {len(validacion)} filas de {len(ids_validacion)} issues -> {args.salida_validacion}")


if __name__ == "__main__":
    main()