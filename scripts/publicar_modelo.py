import argparse
import json
import os
import shutil

import pandas as pd
import torch
from safetensors.torch import load_file, save_file

from bench.variantes import VARIANTES
from triage import limpiar_cuerpo


def convertir(origen, destino):
    if os.path.exists(destino):
        shutil.rmtree(destino)
    os.makedirs(destino)
    pesos = load_file(os.path.join(origen, "model.safetensors"))
    medios = {k: (v.to(torch.bfloat16) if v.is_floating_point() else v).contiguous() for k, v in pesos.items()}
    save_file(medios, os.path.join(destino, "model.safetensors"))
    for sub in ("encoder", "tokenizer"):
        shutil.copytree(os.path.join(origen, sub), os.path.join(destino, sub))
    shutil.copy(os.path.join(origen, "rl_agent_config.json"), destino)
    tamano = lambda ruta: os.path.getsize(os.path.join(ruta, "model.safetensors")) / 1e9
    print(f"Pesos: {tamano(origen):.2f} GB en float32 -> {tamano(destino):.2f} GB en bf16")


def verificar(origen, destino, validacion, cantidad, dispositivo):
    from laya import Agent

    datos = pd.read_csv(validacion).fillna("").head(cantidad)
    estados = [{"title": str(t), "body": limpiar_cuerpo(str(c))} for t, c in zip(datos["title"], datos["body"])]
    pregunta = {"tipo": VARIANTES["sin_other"]}
    respuestas = {}
    for nombre, ruta in (("float32", origen), ("bf16", destino)):
        agente = Agent(ruta, device=dispositivo)
        respuestas[nombre] = [r["answers"]["tipo"] for r in agente.predict_batch(estados, pregunta, batch_size=16)]
        del agente
    iguales = sum(a["choice"] == b["choice"] for a, b in zip(respuestas["float32"], respuestas["bf16"]))
    diferencia = max(abs(a["answer_confidence"] - b["answer_confidence"]) for a, b in zip(respuestas["float32"], respuestas["bf16"]))
    print(f"Misma respuesta en {iguales}/{len(estados)} issues ({iguales / len(estados):.1%}); "
          f"diferencia máxima de confianza {diferencia:.4f}")
    return iguales / len(estados)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("modelo")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--destino", required=True)
    parser.add_argument("--tarjeta", required=True)
    parser.add_argument("--validacion", default="datos/validacion.csv")
    parser.add_argument("--verificar", type=int, default=200)
    parser.add_argument("--dispositivo", default="cpu")
    parser.add_argument("--subir", action="store_true")
    args = parser.parse_args()

    convertir(args.modelo, args.destino)
    shutil.copy(args.tarjeta, os.path.join(args.destino, "README.md"))
    with open(os.path.join(args.destino, "rl_agent_config.json"), encoding="utf-8") as archivo:
        info = json.load(archivo).get("laya_triage", {})
    print(f"Calibración incluida: temperatura y priores {info.get('priores')}")

    if args.verificar:
        coincidencia = verificar(args.modelo, args.destino, args.validacion, args.verificar, args.dispositivo)
        if coincidencia < 0.98:
            raise SystemExit("La versión bf16 cambia demasiadas respuestas: no se sube")

    if not args.subir:
        print(f"Listo en {args.destino}. Revisa y vuelve a correr con --subir")
        return
    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("Falta HF_TOKEN: ponlo en la terminal con set HF_TOKEN=...")
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(args.repo, repo_type="model", exist_ok=True)
    api.upload_folder(folder_path=args.destino, repo_id=args.repo, commit_message="Upload laya-triage model")
    print(f"Publicado en https://huggingface.co/{args.repo}")


if __name__ == "__main__":
    main()
