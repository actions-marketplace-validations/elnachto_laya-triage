import argparse
from collections import Counter

import pandas as pd
import torch
from laya import Router

from bench.variantes import VARIANTES
from triage import limpiar_cuerpo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra", nargs="?", default="datos/calidad/validacion_reciente.csv")
    parser.add_argument("--modelo-ingles", required=True)
    parser.add_argument("--modelo-multilingue", required=True)
    parser.add_argument("--por-defecto", default="multilingual", choices=["multilingual", "english"])
    parser.add_argument("--ejemplos", type=int, default=15)
    args = parser.parse_args()

    datos = pd.read_csv(args.muestra).fillna("")
    peticiones = [
        {"state": {"title": str(t), "body": limpiar_cuerpo(str(b))}, "questions": {"tipo": VARIANTES["sin_other"]}}
        for t, b in zip(datos["title"], datos["body"])
    ]
    router = Router(
        models={"english": args.modelo_ingles, "multilingual": args.modelo_multilingue},
        default=args.por_defecto,
        device="cuda" if torch.cuda.is_available() else "cpu",
    )
    resultados = router.predict_batch(peticiones, batch_size=32)

    multi = [(i, r["routing"]) for i, r in enumerate(resultados) if r["routing"]["model"] == "multilingual"]
    print(f"{len(multi)} de {len(resultados)} issues van a la ruta multilingüe")
    print("\nIdioma detectado:")
    for idioma, n in Counter(ruta["detection"].get("language") for _, ruta in multi).most_common():
        print(f"  {idioma}: {n}")
    print("\nIdioma indeciso:", sum(bool(ruta["detection"].get("language_undecided")) for _, ruta in multi))
    print("\nEscritura:")
    for escritura, n in Counter(ruta["detection"].get("script") for _, ruta in multi).most_common():
        print(f"  {escritura}: {n}")
    print("\nMotivos:")
    for motivo, n in Counter(ruta["reason"] for _, ruta in multi).most_common(10):
        print(f"  {n:5d}  {motivo}")
    print("\nEjemplos:")
    for i, ruta in multi[: args.ejemplos]:
        titulo = str(datos["title"].iloc[i])[:90]
        print(f"  [{ruta['detection'].get('language')}] {titulo}")


if __name__ == "__main__":
    main()