import argparse

import pandas as pd

from entrenamiento.preparar_reciente import COLUMNAS, es_validacion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recientes", nargs="+", default=["datos/calidad/entrenamiento.csv", "datos/calidad/entrenamiento2.csv"])
    parser.add_argument("--traducciones", default="datos/ml_entrenamiento.csv")
    parser.add_argument("--repeticiones-traducciones", type=int, default=3)
    parser.add_argument("--nlbse", default="D:/laya/datos/entrenamiento_1m.csv")
    parser.add_argument("--cantidad-nlbse", type=int, default=100000)
    parser.add_argument("--porcentaje-validacion", type=int, default=5)
    parser.add_argument("--salida", default="D:/laya/datos/conjunto_ml.csv")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    recientes = pd.concat([pd.read_csv(ruta).fillna("") for ruta in args.recientes]).drop_duplicates("id")
    recientes = recientes[~recientes["repo"].map(lambda r: es_validacion(r, args.porcentaje_validacion))]
    print(f"Recientes: {len(recientes)} issues (sin los repos de validación)")

    traducciones = pd.read_csv(args.traducciones).fillna("")
    print(f"Traducciones: {len(traducciones)} issues en {traducciones['idioma'].nunique()} idiomas, repetidas {args.repeticiones_traducciones} veces")

    nlbse = pd.read_csv(args.nlbse, usecols=COLUMNAS).fillna("")
    nlbse = nlbse.sample(min(args.cantidad_nlbse, len(nlbse)), random_state=args.semilla)
    print(f"NLBSE: {len(nlbse)} issues")

    partes = [recientes[COLUMNAS], nlbse[COLUMNAS]] + [traducciones[COLUMNAS]] * args.repeticiones_traducciones
    conjunto = pd.concat(partes).sample(frac=1, random_state=args.semilla)
    conjunto.to_csv(args.salida, index=False)

    mezcla = conjunto["labels"].value_counts(normalize=True)
    print(f"\n{len(conjunto)} filas guardadas en {args.salida}")
    print((mezcla * 100).round(1).to_string())
    base = {"bug": mezcla.get("bug", 0), "feature": mezcla.get("feature", 0),
            "question": mezcla.get("question", 0), "docs": mezcla.get("documentation", 0)}
    print(f"mezcla_base para el modelo: { {k: round(float(v), 3) for k, v in base.items()} }")


if __name__ == "__main__":
    main()