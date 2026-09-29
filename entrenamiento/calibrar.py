import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
from laya.common import collate_items, ece_score

from bench.variantes import VARIANTES
from entrenamiento.entrenar import autocast, adelante, cargar_base, construir_items, mover

PRIORES_REALES = {"bug": 0.526, "feature": 0.370, "question": 0.060, "docs": 0.044}
UMBRALES = [round(u, 2) for u in np.arange(0.40, 0.96, 0.05)]


def obtener_logits(modelo, items, dispositivo, tamano, pad_id):
    modelo.eval()
    salida = []
    with torch.no_grad(), autocast(dispositivo):
        for i in range(0, len(items), tamano):
            lote = collate_items([items[i:i + tamano]], pad_id)
            salida.append(adelante(modelo, mover(lote, dispositivo)).float().cpu())
    return torch.cat(salida).numpy()


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def ajustar_temperatura(logits, etiquetas):
    z = torch.tensor(logits)
    y = torch.tensor(etiquetas)
    log_t = torch.zeros(1, requires_grad=True)
    optimizador = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)

    def cierre():
        optimizador.zero_grad()
        perdida = torch.nn.functional.cross_entropy(z / log_t.exp(), y)
        perdida.backward()
        return perdida

    optimizador.step(cierre)
    return float(torch.clamp(log_t.exp(), 0.5, 5.0).item())


def resumir(probabilidades, etiquetas):
    predichas = probabilidades.argmax(1)
    confianzas = probabilidades.max(1)
    correctas = (predichas == etiquetas).astype(float)
    curva = []
    for umbral in UMBRALES:
        elegidos = confianzas >= umbral
        curva.append({
            "umbral": umbral,
            "cobertura": round(float(elegidos.mean()), 3),
            "precision": round(float(correctas[elegidos].mean()), 3) if elegidos.any() else None,
        })
    return {
        "exactitud": round(float(correctas.mean()), 4),
        "ece": round(ece_score(confianzas, correctas), 4),
        "curva": curva,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default="modelos/laya-triage-en/mejor")
    parser.add_argument("--validacion", default="datos/validacion.csv")
    parser.add_argument("--variante", default="sin_other", choices=sorted(VARIANTES))
    parser.add_argument("--guardar", action="store_true")
    parser.add_argument("--sin-priores", action="store_true")
    parser.add_argument("--nombre", default="calibracion")
    args = parser.parse_args()

    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    cfg, tok, modelo = cargar_base(args.modelo, dispositivo)
    datos = pd.read_csv(args.validacion).fillna("")
    items, claves, _ = construir_items(datos, VARIANTES[args.variante], tok, cfg, 0.0)

    logits = obtener_logits(modelo, items, dispositivo, 32, tok.pad_token_id)
    etiquetas = np.array([it["label"] for it in items])
    ajuste = np.arange(len(items)) % 2 == 0
    prueba = ~ajuste

    temperatura = ajustar_temperatura(logits[ajuste], etiquetas[ajuste])
    log_priores = np.log(np.array([PRIORES_REALES[c] for c in claves]) * len(claves))

    informe = {
        "modelo": args.modelo,
        "temperatura": round(temperatura, 4),
        "issues_ajuste": int(ajuste.sum()),
        "issues_prueba": int(prueba.sum()),
        "sin_calibrar": resumir(softmax(logits[prueba]), etiquetas[prueba]),
        "calibrado": resumir(softmax(logits[prueba] / temperatura), etiquetas[prueba]),
        "calibrado_con_priores": resumir(softmax(logits[prueba] / temperatura + log_priores), etiquetas[prueba]),
    }

    os.makedirs("bench/resultados", exist_ok=True)
    with open(f"bench/resultados/{args.nombre}.json", "w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, indent=2, ensure_ascii=False)
    print(json.dumps(informe, indent=2, ensure_ascii=False))

    if args.guardar:
        ruta = os.path.join(args.modelo, "rl_agent_config.json")
        with open(ruta, encoding="utf-8") as archivo:
            config = json.load(archivo)
        config["temperature"] = [round(temperatura, 4), 1.0, 1.0]
        config.pop("temperature_by_options", None)
        if args.sin_priores:
            config.get("laya_triage", {}).pop("priores", None)
        else:
            config.setdefault("laya_triage", {})["priores"] = {c: PRIORES_REALES[c] for c in claves}
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(config, archivo, indent=2, ensure_ascii=False)
        print(f"Temperatura {temperatura:.4f} guardada en {ruta}" + (" sin priores" if args.sin_priores else " con priores"))


if __name__ == "__main__":
    main()