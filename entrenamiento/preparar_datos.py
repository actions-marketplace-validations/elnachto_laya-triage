import argparse
import os
from collections import Counter

import numpy as np
import pandas as pd

VALIDACION = 5000
MARGEN = 1.3
SEMILLA = 42
TAMANO_BLOQUE = 100_000


def contar_clases(origen):
    conteo = Counter()
    for bloque in pd.read_csv(origen, usecols=["labels"], chunksize=TAMANO_BLOQUE):
        conteo.update(bloque["labels"])
    return conteo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origen")
    parser.add_argument("prueba")
    parser.add_argument("--por-clase", type=int, default=10000)
    parser.add_argument("--salida", default="datos/entrenamiento.csv")
    args = parser.parse_args()

    conteo = contar_clases(args.origen)
    total = sum(conteo.values())
    print(f"{total} issues en el conjunto de entrenamiento: {dict(conteo)}")

    ids_prueba = set(pd.read_csv(args.prueba, usecols=["id"])["id"])
    prob_validacion = VALIDACION * MARGEN / total
    prob_entrenamiento = {c: min(1.0, args.por_clase * MARGEN / n) for c, n in conteo.items()}

    rng = np.random.default_rng(SEMILLA)
    partes_validacion = []
    partes_entrenamiento = []
    repetidos = 0

    for bloque in pd.read_csv(args.origen, chunksize=TAMANO_BLOQUE):
        bloque = bloque.fillna("")
        en_prueba = bloque["id"].isin(ids_prueba)
        repetidos += int(en_prueba.sum())
        bloque = bloque[~en_prueba]

        es_validacion = rng.random(len(bloque)) < prob_validacion
        partes_validacion.append(bloque[es_validacion])

        resto = bloque[~es_validacion]
        umbrales = resto["labels"].map(prob_entrenamiento).to_numpy()
        partes_entrenamiento.append(resto[rng.random(len(resto)) < umbrales])

    validacion = pd.concat(partes_validacion)
    validacion = validacion.sample(n=min(VALIDACION, len(validacion)), random_state=SEMILLA)

    candidatos = pd.concat(partes_entrenamiento)
    entrenamiento = pd.concat(
        grupo.sample(n=min(args.por_clase, len(grupo)), random_state=SEMILLA)
        for _, grupo in candidatos.groupby("labels")
    ).sample(frac=1, random_state=SEMILLA)

    if os.path.exists("datos/validacion.csv"):
        print("datos/validacion.csv ya existe: se conserva sin cambios")
    else:
        validacion.to_csv("datos/validacion.csv", index=False)
    entrenamiento.to_csv(args.salida, index=False)

    print(f"Issues que también estaban en la prueba y se descartaron: {repetidos}")
    print(f"Entrenamiento: {len(entrenamiento)} guardados en {args.salida}")
    print(entrenamiento["labels"].value_counts())


if __name__ == "__main__":
    main()