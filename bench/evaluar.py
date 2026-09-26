import argparse
import json
import os
import time
from collections import Counter

import pandas as pd
import torch
from laya import Router

from bench.variantes import VARIANTES
from triage import UMBRAL_TIPO, limpiar_cuerpo

MAPA_ETIQUETAS = {
    "bug": "bug",
    "feature": "feature",
    "question": "question",
    "documentation": "docs",
}
CLASES = ["bug", "feature", "question", "docs"]


def calcular_metricas(reales, predichas):
    aciertos = sum(r == p for r, p in zip(reales, predichas))
    por_clase = {}
    for clase in CLASES:
        vp = sum(r == clase and p == clase for r, p in zip(reales, predichas))
        fp = sum(r != clase and p == clase for r, p in zip(reales, predichas))
        fn = sum(r == clase and p != clase for r, p in zip(reales, predichas))
        precision = vp / (vp + fp) if vp + fp else 0.0
        recall = vp / (vp + fn) if vp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        por_clase[clase] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "soporte": vp + fn,
        }
    f1_macro = sum(v["f1"] for v in por_clase.values()) / len(CLASES)
    return aciertos / len(reales), f1_macro, por_clase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra")
    parser.add_argument("--nombre", default="laya-base")
    parser.add_argument("--variante", default="actual", choices=sorted(VARIANTES))
    parser.add_argument("--modelo-ingles", default="")
    parser.add_argument("--limite", type=int, default=0)
    parser.add_argument("--lote", type=int, default=32)
    parser.add_argument("--dispositivo", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    pregunta = VARIANTES[args.variante]
    datos = pd.read_csv(args.muestra).fillna("")
    if args.limite:
        datos = datos.head(args.limite)

    peticiones = [
        {"state": {"title": str(titulo), "body": limpiar_cuerpo(str(cuerpo))}, "questions": {"tipo": pregunta}}
        for titulo, cuerpo in zip(datos["title"], datos["body"])
    ]
    reales = [MAPA_ETIQUETAS[etiqueta] for etiqueta in datos["labels"]]

    modelos = {"english": args.modelo_ingles} if args.modelo_ingles else None
    print(f"Evaluando {len(peticiones)} issues en {args.dispositivo} con la variante {args.variante}")
    router = Router(models=modelos, default="multilingual", device=args.dispositivo)
    inicio = time.perf_counter()
    resultados = router.predict_batch(peticiones, batch_size=args.lote)
    segundos = time.perf_counter() - inicio

    predichas = [r["answers"]["tipo"]["choice"] for r in resultados]
    confianzas = [r["answers"]["tipo"]["answer_confidence"] for r in resultados]
    rutas = Counter(r["routing"]["model"] for r in resultados)

    exactitud, f1_macro, por_clase = calcular_metricas(reales, predichas)
    cubiertos = [(r, p) for r, p, c in zip(reales, predichas, confianzas) if c >= UMBRAL_TIPO]
    cobertura = len(cubiertos) / len(reales)
    exactitud_cubiertos = sum(r == p for r, p in cubiertos) / len(cubiertos) if cubiertos else 0.0
    linea_base = Counter(reales).most_common(1)[0][1] / len(reales)

    informe = {
        "modelo": args.nombre,
        "modelo_ingles": args.modelo_ingles or "convaiinnovations/laya",
        "variante": args.variante,
        "dispositivo": args.dispositivo,
        "issues": len(reales),
        "rutas": dict(rutas),
        "exactitud": round(exactitud, 3),
        "f1_macro": round(f1_macro, 3),
        "linea_base_mayoritaria": round(linea_base, 3),
        "umbral": UMBRAL_TIPO,
        "cobertura_con_umbral": round(cobertura, 3),
        "exactitud_con_umbral": round(exactitud_cubiertos, 3),
        "ms_por_issue": round(segundos * 1000 / len(reales), 1),
        "por_clase": por_clase,
        "confusion": Counter(f"{r}->{p}" for r, p in zip(reales, predichas) if r != p).most_common(8),
    }

    os.makedirs("bench/resultados", exist_ok=True)
    with open(f"bench/resultados/{args.nombre}.json", "w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, indent=2, ensure_ascii=False)

    print(json.dumps(informe, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()