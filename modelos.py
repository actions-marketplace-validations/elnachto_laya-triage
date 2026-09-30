import json
import os

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

MODELOS = {
    "english": ("elnachto/laya-triage-en", "2b87cb41ba78f6192c711ab3fd331b6133eadc41"),
    "multilingual": ("elnachto/laya-triage-multilingual", "194786c14ecec3105333662e6e5de8e61b6708ae"),
}

ARCHIVOS = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]


def ruta_modelo(repo, revision):
    try:
        return snapshot_download(repo, revision=revision, allow_patterns=ARCHIVOS, local_files_only=True)
    except LocalEntryNotFoundError:
        return snapshot_download(repo, revision=revision, allow_patterns=ARCHIVOS)


def rutas_modelos():
    return {nombre: ruta_modelo(repo, revision) for nombre, (repo, revision) in MODELOS.items()}


def leer_config_triage(carpeta):
    with open(os.path.join(carpeta, "rl_agent_config.json"), encoding="utf-8") as archivo:
        return json.load(archivo).get("laya_triage", {})


def leer_priores(carpeta):
    return leer_config_triage(carpeta).get("priores")


def leer_mezcla_base(carpeta):
    return leer_config_triage(carpeta).get("mezcla_base")


if __name__ == "__main__":
    for nombre, carpeta in rutas_modelos().items():
        print(f"{nombre}: {carpeta}")
