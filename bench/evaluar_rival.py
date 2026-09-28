import argparse
import json
import os
import time
from collections import Counter

import pandas as pd
import torch
from laya import Agent

from bench.evaluar import MAPA_ETIQUETAS, calcular_metricas

A_NUESTRAS = {"bug": "bug", "feature": "feature", "question": "question", "docs": "docs"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra")
    parser.add_argument("--nombre", default="rival")
    parser.add_argument("--modelo", default="harikarthikmanyam/laya-issue-triage")
    parser.add_argument("--preguntas", default="../rival/config/questions.json")
    parser.add_argument("--max-caracteres", type=int, default=900)
    parser.add_argument("--lote", type=int, default=32)
    parser.add_argument("--dispositivo", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    with open(args.preguntas, encoding="utf-8") as archivo:
        pregunta = json.load(archivo)["issue_type"]
    datos = pd.read_csv(args.muestra).fillna("")
    estados = [{"title": str(t), "body": str(c)[:args.max_caracteres]} for t, c in zip(datos["title"], datos["body"])]
    reales = [MAPA_ETIQUETAS[etiqueta] for etiqueta in datos["labels"]]

    agente = Agent(args.modelo, device=args.dispositivo)
    inicio = time.perf_counter()
    resultados = agente.predict_batch(estados, {"issue_type": pregunta}, batch_size=args.lote)
    segundos = time.perf_counter() - inicio

    predichas = [A_NUESTRAS[r["answers"]["issue_type"]["choice"]] for r in resultados]
    confianzas = [r["answers"]["issue_type"]["answer_confidence"] for r in resultados]
    exactitud, f1_macro, por_clase = calcular_metricas(reales, predichas)
    cubiertos = [(r, p) for r, p, c in zip(reales, predichas, confianzas) if c >= 0.60]

    informe = {
        "modelo": args.nombre,
        "checkpoint": args.modelo,
        "issues": len(reales),
        "exactitud": round(exactitud, 3),
        "f1_macro": round(f1_macro, 3),
        "cobertura_con_umbral": round(len(cubiertos) / len(reales), 3),
        "exactitud_con_umbral": round(sum(r == p for r, p in cubiertos) / max(1, len(cubiertos)), 3),
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