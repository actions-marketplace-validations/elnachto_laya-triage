import sys
from collections import Counter

import numpy as np
import pandas as pd

POR_CLASE = 10000
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
    origen = sys.argv[1]
    prueba = sys.argv[2]

    conteo = contar_clases(origen)
    total = sum(conteo.values())
    print(f"{total} issues en el conjunto de entrenamiento: {dict(conteo)}")

    ids_prueba = set(pd.read_csv(prueba, usecols=["id"])["id"])
    prob_validacion = VALIDACION * MARGEN / total
    prob_entrenamiento = {c: min(1.0, POR_CLASE * MARGEN / n) for c, n in conteo.items()}

    rng = np.random.default_rng(SEMILLA)
    partes_validacion = []
    partes_entrenamiento = []
    repetidos = 0

    for bloque in pd.read_csv(origen, chunksize=TAMANO_BLOQUE):
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
        grupo.sample(n=min(POR_CLASE, len(grupo)), random_state=SEMILLA)
        for _, grupo in candidatos.groupby("labels")
    ).sample(frac=1, random_state=SEMILLA)

    validacion.to_csv("datos/validacion.csv", index=False)
    entrenamiento.to_csv("datos/entrenamiento.csv", index=False)

    print(f"Issues que también estaban en la prueba y se descartaron: {repetidos}")
    print(f"Validación: {len(validacion)}")
    print(validacion["labels"].value_counts())
    print(f"Entrenamiento: {len(entrenamiento)}")
    print(entrenamiento["labels"].value_counts())


if __name__ == "__main__":
    main()