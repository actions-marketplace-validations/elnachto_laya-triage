import json
import os

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

MODELOS = {
    "english": ("elnachto/laya-triage-en", "7d514587f82a14d72ae5850d96bf6c5c28897b39"),
    "multilingual": ("elnachto/laya-triage-multilingual", "cdb5ce1293d2c570af22bfb3af406535da6906ae"),
}

ARCHIVOS = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]


def ruta_modelo(repo, revision):
    try:
        return snapshot_download(repo, revision=revision, allow_patterns=ARCHIVOS, local_files_only=True)
    except LocalEntryNotFoundError:
        return snapshot_download(repo, revision=revision, allow_patterns=ARCHIVOS)


def rutas_modelos():
    return {nombre: ruta_modelo(repo, revision) for nombre, (repo, revision) in MODELOS.items()}


def leer_priores(carpeta):
    with open(os.path.join(carpeta, "rl_agent_config.json"), encoding="utf-8") as archivo:
        return json.load(archivo).get("laya_triage", {}).get("priores")


if __name__ == "__main__":
    for nombre, carpeta in rutas_modelos().items():
        print(f"{nombre}: {carpeta}")