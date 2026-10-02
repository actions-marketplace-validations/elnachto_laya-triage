import argparse

import pandas as pd

from entrenamiento.preparar_reciente import COLUMNAS, es_validacion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recientes", nargs="+", default=["datos/calidad/entrenamiento.csv", "datos/calidad/entrenamiento2.csv"])
    parser.add_argument("--nlbse", default="D:/laya/datos/entrenamiento_1m.csv")
    parser.add_argument("--repeticiones", type=int, default=2)
    parser.add_argument("--porcentaje-validacion", type=int, default=5)
    parser.add_argument("--salida", default="D:/laya/datos/conjunto.csv")
    parser.add_argument("--salida-validacion", default="datos/calidad/validacion_conjunta.csv")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    recientes = pd.concat([pd.read_csv(ruta).fillna("") for ruta in args.recientes])
    antes = len(recientes)
    recientes = recientes.drop_duplicates("id")
    print(f"Recientes: {len(recientes)} issues de {recientes['repo'].nunique()} repos ({antes - len(recientes)} duplicados quitados)")

    en_validacion = recientes["repo"].map(lambda r: es_validacion(r, args.porcentaje_validacion))
    validacion = recientes[en_validacion]
    recientes = recientes[~en_validacion]
    print(f"  {len(recientes)} para entrenar y {len(validacion)} para validar ({validacion['repo'].nunique()} repos que el entrenamiento no ve)")

    nlbse = pd.read_csv(args.nlbse, usecols=COLUMNAS).fillna("")
    print(f"NLBSE: {len(nlbse)} issues")

    partes = [nlbse[COLUMNAS]] + [recientes[COLUMNAS]] * args.repeticiones
    conjunto = pd.concat(partes).sample(frac=1, random_state=args.semilla)
    conjunto.to_csv(args.salida, index=False)
    validacion[COLUMNAS + ["repo"]].to_csv(args.salida_validacion, index=False)

    mezcla = conjunto["labels"].value_counts(normalize=True)
    print(f"\n{len(conjunto)} filas guardadas en {args.salida} (recientes repetidos {args.repeticiones} veces)")
    print((mezcla * 100).round(1).to_string())
    base = {"bug": mezcla.get("bug", 0), "feature": mezcla.get("feature", 0),
            "question": mezcla.get("question", 0), "docs": mezcla.get("documentation", 0)}
    print(f"mezcla_base para el modelo: { {k: round(float(v), 3) for k, v in base.items()} }")
    print(f"{len(validacion)} issues de validación guardados en {args.salida_validacion}")


if __name__ == "__main__":
    main()