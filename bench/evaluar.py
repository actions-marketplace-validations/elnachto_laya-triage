import argparse
import json
import os
import time
from collections import Counter

import pandas as pd
import torch
from laya import Router

from bench.variantes import VARIANTES
from repo import mezcla_desde_conteos, pesos_para_ruta
from triage import UMBRAL_TIPO, limpiar_cuerpo

MAPA_ETIQUETAS = {
    "bug": "bug",
    "feature": "feature",
    "question": "question",
    "documentation": "docs",
}
CLASES = ["bug", "feature", "question", "docs"]
MEZCLA_NATURAL = {"bug": 0.526, "feature": 0.370, "question": 0.060, "docs": 0.044}


def leer_objetivo(texto):
    valores = {}
    for parte in texto.split(","):
        clase, valor = parte.split("=")
        valores[clase.strip()] = float(valor)
    total = sum(valores.values())
    return {clase: valor / total for clase, valor in valores.items()}


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


def leer_priores(carpeta_modelo):
    ruta = os.path.join(carpeta_modelo, "rl_agent_config.json")
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo).get("laya_triage", {}).get("priores")


def aplicar_priores(respuesta, priores):
    ajustadas = {k: p * priores.get(k, 1.0) for k, p in respuesta["probabilities"].items()}
    total = sum(ajustadas.values()) or 1.0
    ajustadas = {k: v / total for k, v in ajustadas.items()}
    eleccion = max(ajustadas, key=ajustadas.get)
    return eleccion, ajustadas[eleccion]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra")
    parser.add_argument("--nombre", default="laya-base")
    parser.add_argument("--variante", default="sin_other", choices=sorted(VARIANTES))
    parser.add_argument("--modelo-ingles", default="")
    parser.add_argument("--modelo-multilingue", default="")
    parser.add_argument("--limite", type=int, default=0)
    parser.add_argument("--lote", type=int, default=32)
    parser.add_argument("--dispositivo", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--priores", action="store_true")
    parser.add_argument("--priores-objetivo", default="")
    parser.add_argument("--priores-por-repo", action="store_true")
    parser.add_argument("--por-defecto", default="multilingual", choices=["multilingual", "english"])
    args = parser.parse_args()

    rutas_modelo = {"english": args.modelo_ingles, "multilingual": args.modelo_multilingue}
    rutas_modelo = {ruta: carpeta for ruta, carpeta in rutas_modelo.items() if carpeta}
    if args.priores and not rutas_modelo:
        raise SystemExit("--priores necesita --modelo-ingles o --modelo-multilingue")
    priores = {ruta: leer_priores(carpeta) for ruta, carpeta in rutas_modelo.items()} if args.priores else {}
    priores = {ruta: valores for ruta, valores in priores.items() if valores}
    if args.priores_objetivo:
        objetivo = leer_objetivo(args.priores_objetivo)
        priores = {
            ruta: (objetivo if ruta in priores else {c: objetivo[c] / MEZCLA_NATURAL[c] for c in objetivo})
            for ruta in rutas_modelo
        }
        print(f"Mezcla objetivo: {objetivo}")
    if args.priores:
        for ruta in rutas_modelo:
            print(f"Ruta {ruta}: {'con priores' if ruta in priores else 'sin priores'}")

    pregunta = VARIANTES[args.variante]
    datos = pd.read_csv(args.muestra).fillna("")
    if args.limite:
        datos = datos.head(args.limite)

    peticiones = [
        {"state": {"title": str(titulo), "body": limpiar_cuerpo(str(cuerpo))}, "questions": {"tipo": pregunta}}
        for titulo, cuerpo in zip(datos["title"], datos["body"])
    ]
    reales = [MAPA_ETIQUETAS[etiqueta] for etiqueta in datos["labels"]]

    modelos = rutas_modelo or None
    print(f"Evaluando {len(peticiones)} issues en {args.dispositivo} con la variante {args.variante}")
    router = Router(models=modelos, default=args.por_defecto, device=args.dispositivo)
    inicio = time.perf_counter()
    resultados = router.predict_batch(peticiones, batch_size=args.lote)
    segundos = time.perf_counter() - inicio

    por_repo = []
    if args.priores_por_repo:
        conteos_repo = {}
        for repo_issue, real in zip(datos["repo"], reales):
            conteos_repo.setdefault(repo_issue, {c: 0 for c in CLASES})[real] += 1
        for repo_issue, real in zip(datos["repo"], reales):
            historial = dict(conteos_repo[repo_issue])
            historial[real] -= 1
            por_repo.append(mezcla_desde_conteos(historial))
        adaptados = sum(m is not None for m in por_repo)
        print(f"Issues con historial suficiente en su repo: {adaptados} de {len(por_repo)}")

    predichas = []
    confianzas = []
    for i, r in enumerate(resultados):
        respuesta = r["answers"]["tipo"]
        ruta = r["routing"]["model"]
        if por_repo and por_repo[i]:
            eleccion, confianza = aplicar_priores(respuesta, pesos_para_ruta(por_repo[i], priores.get(ruta)))
        elif ruta in priores:
            eleccion, confianza = aplicar_priores(respuesta, priores[ruta])
        else:
            eleccion, confianza = respuesta["choice"], respuesta["answer_confidence"]
        predichas.append(eleccion)
        confianzas.append(confianza)
    rutas = Counter(r["routing"]["model"] for r in resultados)
    por_ruta = {}
    for nombre_ruta in rutas:
        indices = [i for i, r in enumerate(resultados) if r["routing"]["model"] == nombre_ruta]
        exactitud_ruta, f1_ruta, _ = calcular_metricas([reales[i] for i in indices], [predichas[i] for i in indices])
        por_ruta[nombre_ruta] = {"issues": len(indices), "exactitud": round(exactitud_ruta, 3), "f1_macro": round(f1_ruta, 3)}

    exactitud, f1_macro, por_clase = calcular_metricas(reales, predichas)
    cubiertos = [(r, p) for r, p, c in zip(reales, predichas, confianzas) if c >= UMBRAL_TIPO]
    cobertura = len(cubiertos) / len(reales)
    exactitud_cubiertos = sum(r == p for r, p in cubiertos) / len(cubiertos) if cubiertos else 0.0
    linea_base = Counter(reales).most_common(1)[0][1] / len(reales)

    informe = {
        "modelo": args.nombre,
        "modelo_ingles": args.modelo_ingles or "convaiinnovations/laya",
        "modelo_multilingue": args.modelo_multilingue or "convaiinnovations/laya/multilingual",
        "variante": args.variante,
        "por_defecto": args.por_defecto,
        "priores": priores,
        "dispositivo": args.dispositivo,
        "issues": len(reales),
        "rutas": dict(rutas),
        "por_ruta": por_ruta,
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