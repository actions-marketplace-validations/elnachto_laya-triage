import argparse
import json
import math
import os
import random
import shutil
import time

import pandas as pd
import torch
from huggingface_hub import snapshot_download
from laya.agent import _fix_tokenizer_config, _load_tokenizer
from laya.common import QTYPES, build_model, build_sequence, collate_items, proper_reward
from safetensors.torch import load_file, save_file
from tqdm import tqdm
from transformers import get_linear_schedule_with_warmup

from bench.evaluar import MAPA_ETIQUETAS, calcular_metricas
from bench.variantes import VARIANTES
from triage import limpiar_cuerpo

ARCHIVOS_BASE = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]


def resolver_base(base):
    carpeta = base if os.path.isdir(base) else snapshot_download(base, allow_patterns=ARCHIVOS_BASE)
    _fix_tokenizer_config(carpeta)
    return carpeta


def cargar_base(carpeta, dispositivo):
    with open(os.path.join(carpeta, "rl_agent_config.json"), encoding="utf-8") as archivo:
        cfg = json.load(archivo)
    tok = _load_tokenizer(os.path.join(carpeta, "tokenizer"), cfg)
    modelo = build_model(cfg, encoder_dir=os.path.join(carpeta, "encoder"), pretrained=False)
    modelo.load_state_dict(load_file(os.path.join(carpeta, "model.safetensors")), strict=True)
    try:
        modelo.encoder.config.reference_compile = False
    except Exception:
        pass
    return cfg, tok, modelo.to(dispositivo)


def construir_items(datos, pregunta, tok, cfg, suavizado):
    interna = {"t": "choice", "ins": pregunta["instructions"], "crit": pregunta["criteria"]}
    claves = list(pregunta["criteria"])
    k = len(claves)
    items = []
    descartados = 0
    for titulo, cuerpo, etiqueta in zip(datos["title"], datos["body"], datos["labels"]):
        estado = {"title": str(titulo), "body": limpiar_cuerpo(str(cuerpo))}
        ids, marcadores = build_sequence(
            tok, estado, interna, cfg.get("max_len", 512), cfg.get("head_max_len", 192)
        )
        if len(marcadores) != k:
            descartados += 1
            continue
        correcta = claves.index(MAPA_ETIQUETAS[etiqueta])
        objetivo = [suavizado / (k - 1)] * k
        objetivo[correcta] = 1.0 - suavizado
        items.append({
            "ids": ids,
            "markers": marcadores,
            "qtype": QTYPES["choice"],
            "target": objetivo,
            "label": correcta,
        })
    return items, claves, descartados


def mover(lote, dispositivo):
    return {k: v.to(dispositivo) for k, v in lote.items() if torch.is_tensor(v)}


def autocast(dispositivo):
    return torch.autocast(
        device_type="cuda" if dispositivo == "cuda" else "cpu",
        dtype=torch.bfloat16,
        enabled=dispositivo == "cuda",
    )


def adelante(modelo, t):
    logits, _ = modelo(t["input_ids"], t["attention_mask"], t["marker_pos"], t["marker_mask"], t["qtype"])
    return logits


def evaluar(modelo, items, claves, dispositivo, tamano, pad_id):
    modelo.eval()
    predichas = []
    with torch.no_grad(), autocast(dispositivo):
        for i in range(0, len(items), tamano):
            lote = collate_items([items[i:i + tamano]], pad_id)
            logits = adelante(modelo, mover(lote, dispositivo))
            predichas.extend(logits.argmax(-1).tolist())
    modelo.train()
    reales = [claves[it["label"]] for it in items]
    exactitud, f1_macro, por_clase = calcular_metricas(reales, [claves[p] for p in predichas])
    return round(exactitud, 4), round(f1_macro, 4), por_clase


def guardar_modelo(modelo, cfg, carpeta_base, destino, info):
    os.makedirs(destino, exist_ok=True)
    pesos = {k: v.detach().cpu().contiguous() for k, v in modelo.state_dict().items()}
    save_file(pesos, os.path.join(destino, "model.safetensors"))
    for sub in ("encoder", "tokenizer"):
        shutil.copytree(os.path.join(carpeta_base, sub), os.path.join(destino, sub), dirs_exist_ok=True)
    nuevo = dict(cfg)
    nuevo["temperature"] = [1.0, 1.0, 1.0]
    nuevo.pop("temperature_by_options", None)
    nuevo["laya_triage"] = info
    with open(os.path.join(destino, "rl_agent_config.json"), "w", encoding="utf-8") as archivo:
        json.dump(nuevo, archivo, indent=2, ensure_ascii=False)


def leer_csv(ruta, limite):
    datos = pd.read_csv(ruta).fillna("")
    return datos.head(limite) if limite else datos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="convaiinnovations/laya")
    parser.add_argument("--entrenamiento", default="datos/entrenamiento.csv")
    parser.add_argument("--validacion", default="datos/validacion.csv")
    parser.add_argument("--salida", default="modelos/laya-triage-en")
    parser.add_argument("--variante", default="sin_other", choices=sorted(VARIANTES))
    parser.add_argument("--epocas", type=int, default=3)
    parser.add_argument("--micro-lote", type=int, default=8)
    parser.add_argument("--acumulacion", type=int, default=4)
    parser.add_argument("--lr-encoder", type=float, default=2.5e-5)
    parser.add_argument("--lr-cabeza", type=float, default=1e-4)
    parser.add_argument("--suavizado", type=float, default=0.1)
    parser.add_argument("--calentamiento", type=float, default=0.06)
    parser.add_argument("--limite", type=int, default=0)
    parser.add_argument("--limite-validacion", type=int, default=0)
    parser.add_argument("--sin-checkpointing", action="store_true")
    parser.add_argument("--reanudar", action="store_true")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.semilla)
    torch.manual_seed(args.semilla)
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Dispositivo: {dispositivo}")

    carpeta_base = resolver_base(args.base)
    cfg, tok, modelo = cargar_base(carpeta_base, dispositivo)
    if not args.sin_checkpointing:
        modelo.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        modelo.head_checkpointing = True
    modelo.train()

    pregunta = VARIANTES[args.variante]
    inicio = time.perf_counter()
    items, claves, descartados = construir_items(
        leer_csv(args.entrenamiento, args.limite), pregunta, tok, cfg, args.suavizado
    )
    items_val, _, _ = construir_items(
        leer_csv(args.validacion, args.limite_validacion), pregunta, tok, cfg, 0.0
    )
    print(f"Tokenizados {len(items)} de entrenamiento y {len(items_val)} de validación "
          f"en {time.perf_counter() - inicio:.0f} s (descartados: {descartados})")

    pad_id = tok.pad_token_id
    params_encoder = [p for n, p in modelo.named_parameters() if n.startswith("encoder.")]
    params_cabeza = [p for n, p in modelo.named_parameters() if not n.startswith("encoder.")]
    optimizador = torch.optim.AdamW(
        [{"params": params_encoder, "lr": args.lr_encoder}, {"params": params_cabeza, "lr": args.lr_cabeza}],
        weight_decay=0.01,
    )
    pasos_por_epoca = math.ceil(len(items) / (args.micro_lote * args.acumulacion))
    pasos_totales = pasos_por_epoca * args.epocas
    planificador = get_linear_schedule_with_warmup(
        optimizador, int(pasos_totales * args.calentamiento), pasos_totales
    )

    os.makedirs(args.salida, exist_ok=True)
    ruta_estado = os.path.join(args.salida, "estado.pt")
    ruta_historial = os.path.join(args.salida, "historial.json")
    historial = []
    mejor = -1.0
    epoca_inicial = 1

    if args.reanudar and os.path.exists(ruta_estado):
        estado = torch.load(ruta_estado, map_location=dispositivo, weights_only=False)
        modelo.load_state_dict(estado["modelo"])
        optimizador.load_state_dict(estado["optimizador"])
        planificador.load_state_dict(estado["planificador"])
        historial = estado["historial"]
        mejor = estado["mejor"]
        epoca_inicial = estado["epoca"] + 1
        print(f"Reanudando desde la época {epoca_inicial}")
    else:
        exactitud, f1_macro, _ = evaluar(modelo, items_val, claves, dispositivo, 32, pad_id)
        historial.append({"epoca": 0, "exactitud": exactitud, "f1_macro": f1_macro})
        print(f"Antes de entrenar: exactitud {exactitud} | F1 macro {f1_macro}")

    for epoca in range(epoca_inicial, args.epocas + 1):
        generador = torch.Generator().manual_seed(args.semilla + epoca)
        orden = torch.randperm(len(items), generator=generador).tolist()
        tramos = list(range(0, len(orden), args.micro_lote))
        optimizador.zero_grad(set_to_none=True)
        suma_perdida = 0.0
        barra = tqdm(tramos, desc=f"Época {epoca}/{args.epocas}", unit="lote")

        for n, i in enumerate(barra):
            lote = collate_items([[items[j] for j in orden[i:i + args.micro_lote]]], pad_id)
            t = mover(lote, dispositivo)
            with autocast(dispositivo):
                logits = adelante(modelo, t)
            q = torch.softmax(logits.float(), -1)
            perdida = -proper_reward(q, t["target"], t["qtype"], t["marker_mask"].float()).mean()
            (perdida / args.acumulacion).backward()
            suma_perdida += perdida.item()

            if (n + 1) % args.acumulacion == 0 or n + 1 == len(tramos):
                torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
                optimizador.step()
                planificador.step()
                optimizador.zero_grad(set_to_none=True)
            if (n + 1) % 50 == 0:
                barra.set_postfix(perdida=f"{suma_perdida / (n + 1):.4f}")

        exactitud, f1_macro, por_clase = evaluar(modelo, items_val, claves, dispositivo, 32, pad_id)
        registro = {
            "epoca": epoca,
            "perdida": round(suma_perdida / len(tramos), 4),
            "exactitud": exactitud,
            "f1_macro": f1_macro,
            "por_clase": por_clase,
        }
        historial.append(registro)
        print(f"Época {epoca}: exactitud {exactitud} | F1 macro {f1_macro} | pérdida {registro['perdida']}")

        info = {"variante": args.variante, "epoca": epoca, "validacion": {"exactitud": exactitud, "f1_macro": f1_macro}}
        guardar_modelo(modelo, cfg, carpeta_base, os.path.join(args.salida, f"epoca_{epoca}"), info)
        if exactitud > mejor:
            mejor = exactitud
            guardar_modelo(modelo, cfg, carpeta_base, os.path.join(args.salida, "mejor"), info)
            print("Nuevo mejor modelo guardado")

        torch.save({
            "modelo": modelo.state_dict(),
            "optimizador": optimizador.state_dict(),
            "planificador": planificador.state_dict(),
            "historial": historial,
            "mejor": mejor,
            "epoca": epoca,
        }, ruta_estado)
        with open(ruta_historial, "w", encoding="utf-8") as archivo:
            json.dump(historial, archivo, indent=2, ensure_ascii=False)

    print(f"Listo. Mejor exactitud en validación: {mejor}")


if __name__ == "__main__":
    main()