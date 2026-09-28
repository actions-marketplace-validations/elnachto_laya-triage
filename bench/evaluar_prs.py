import argparse
import json
import os
import time

import numpy as np
import pandas as pd
import torch
from laya import Router

from bench.senales_prs import filtrar
from preguntas import PREGUNTAS_PR
from triage import UMBRAL_SPAM, decidir_pr, es_cambio_trivial, limpiar_cuerpo

UMBRALES = [round(u, 2) for u in np.arange(0.50, 0.96, 0.05)]
LIMITE_DIFF = 800


def resumir_cambios(pr):
    archivos = json.loads(pr.get("archivos") or "[]")
    cabecera = f"{pr['changed_files']} files changed, +{pr['additions']} -{pr['deletions']}: {', '.join(archivos[:10])}"
    return f"{cabecera}\n{str(pr.get('parche') or '')[:LIMITE_DIFF]}"


def construir_estado(pr, con_diff):
    estado = {"title": str(pr["title"]), "body": limpiar_cuerpo(str(pr["body"]))}
    if con_diff:
        estado["changes"] = resumir_cambios(pr)
    return estado


def medir(reales, marcados):
    reales = np.asarray(reales, dtype=bool)
    marcados = np.asarray(marcados, dtype=bool)
    vp = int((reales & marcados).sum())
    fp = int((~reales & marcados).sum())
    fn = int((reales & ~marcados).sum())
    precision = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "falsos_positivos": fp,
        "genuinos_marcados_pct": round(fp / max(1, int((~reales).sum())) * 100, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra", nargs="?", default="datos/prs_hacktoberfest.csv")
    parser.add_argument("--nombre", default="prs_base")
    parser.add_argument("--lote", type=int, default=32)
    parser.add_argument("--dispositivo", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--hilos", type=int, default=4)
    parser.add_argument("--limite", type=int, default=0)
    parser.add_argument("--origen", default="todos", choices=["todos", "spam", "invalid"])
    parser.add_argument("--sin-practica", action="store_true")
    parser.add_argument("--anio", default="")
    parser.add_argument("--con-diff", action="store_true")
    args = parser.parse_args()

    if args.dispositivo == "cpu":
        torch.set_num_threads(args.hilos)

    datos = filtrar(pd.read_csv(args.muestra).fillna(""), args)
    if args.limite:
        datos = datos.head(args.limite)
    prs = datos.to_dict("records")
    reales = [fila["labels"] == "spam" for fila in prs]

    peticiones = [{"state": construir_estado(pr, args.con_diff), "questions": PREGUNTAS_PR} for pr in prs]
    print(f"Evaluando {len(peticiones)} PRs en {args.dispositivo}")
    router = Router(default="multilingual", device=args.dispositivo)
    inicio = time.perf_counter()
    resultados = router.predict_batch(peticiones, batch_size=args.lote)
    segundos = time.perf_counter() - inicio

    prob_spam = [r["answers"]["spam"]["probabilities"].get("B", 0.0) for r in resultados]
    triviales = [es_cambio_trivial(pr) for pr in prs]
    actuales = [bool(decidir_pr(pr, r["answers"])[0]) for pr, r in zip(prs, resultados)]

    curva = []
    for umbral in UMBRALES:
        modelo = [p >= umbral for p in prob_spam]
        curva.append({
            "umbral": umbral,
            "solo_modelo": medir(reales, modelo),
            "modelo_y_trivial": medir(reales, [m and t for m, t in zip(modelo, triviales)]),
        })

    tabla = pd.DataFrame({"real": ["spam" if r else "genuino" for r in reales], "prob": prob_spam, "trivial": triviales})
    informe = {
        "modelo": args.nombre,
        "filtros": {"origen": args.origen, "sin_practica": args.sin_practica, "anio": args.anio, "con_diff": args.con_diff},
        "prs": len(prs),
        "spam": int(sum(reales)),
        "genuinos": len(prs) - int(sum(reales)),
        "umbral_spam_actual": UMBRAL_SPAM,
        "ms_por_pr": round(segundos * 1000 / len(prs), 1),
        "triviales_por_clase_pct": (tabla.groupby("real")["trivial"].mean() * 100).round(1).to_dict(),
        "prob_spam_mediana_por_clase": tabla.groupby("real")["prob"].median().round(3).to_dict(),
        "regla_actual": medir(reales, actuales),
        "solo_regla_trivial": medir(reales, triviales),
        "curva": curva,
        "spam_no_detectado": [pr["title"][:90] for pr, r, a in zip(prs, reales, actuales) if r and not a][:10],
        "genuinos_marcados": [pr["title"][:90] for pr, r, a in zip(prs, reales, actuales) if not r and a][:10],
    }

    os.makedirs("bench/resultados", exist_ok=True)
    with open(f"bench/resultados/{args.nombre}.json", "w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in informe.items() if k != "curva"}, indent=2, ensure_ascii=False))
    print("Curva (umbral: solo modelo F1 | modelo y trivial F1)")
    for punto in curva:
        print(f"  {punto['umbral']:.2f}: {punto['solo_modelo']['f1']:.3f} | {punto['modelo_y_trivial']['f1']:.3f}")


if __name__ == "__main__":
    main()