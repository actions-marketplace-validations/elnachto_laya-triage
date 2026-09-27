import base64
import json
import re
import urllib.error
import urllib.request

import yaml

CARPETAS_PLANTILLAS = [".github/ISSUE_TEMPLATE", ".github", "docs", ""]
NOMBRES_SUELTOS = {"issue_template.md", "bug_report.md", "feature_request.md"}
FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.DOTALL)


def normalizar(linea):
    texto = linea.strip().lower()
    texto = re.sub(r"^(#{1,6}\s*|[-*]\s*\[[ x]\]\s*|[-*]\s+|\d+\.\s+|>\s*)", "", texto)
    texto = re.sub(r"[*_`]", "", texto)
    return re.sub(r"\s+", " ", texto).strip(" :")


def lineas_de_markdown(texto):
    texto = FRONT_MATTER.sub("", texto)
    texto = COMENTARIO_HTML.sub("", texto)
    return {n for n in (normalizar(linea) for linea in texto.splitlines()) if n}


def lineas_de_formulario(texto):
    try:
        formulario = yaml.safe_load(texto) or {}
    except yaml.YAMLError:
        return set()
    lineas = set()
    for campo in formulario.get("body") or []:
        atributos = campo.get("attributes") or {}
        for clave in ("label", "value"):
            valor = atributos.get(clave)
            if isinstance(valor, str):
                lineas |= lineas_de_markdown(valor)
        for opcion in atributos.get("options") or []:
            etiqueta = opcion.get("label") if isinstance(opcion, dict) else opcion
            if isinstance(etiqueta, str):
                lineas.add(normalizar(etiqueta))
    lineas.discard("")
    return lineas


def lineas_de_plantilla(nombre, texto):
    nombre = nombre.lower()
    if nombre.endswith((".yml", ".yaml")):
        return lineas_de_formulario(texto)
    if nombre.endswith(".md"):
        return lineas_de_markdown(texto)
    return set()


def pedir_json(url, token=None):
    cabeceras = {"Accept": "application/vnd.github+json", "User-Agent": "laya-triage"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            return json.load(respuesta)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def cargar_plantillas(repo, token=None):
    lineas = set()
    for carpeta in CARPETAS_PLANTILLAS:
        listado = pedir_json(f"https://api.github.com/repos/{repo}/contents/{carpeta}", token)
        if not isinstance(listado, list):
            continue
        for entrada in listado:
            nombre = entrada.get("name", "")
            es_plantilla = carpeta.endswith("ISSUE_TEMPLATE") or nombre.lower() in NOMBRES_SUELTOS
            if entrada.get("type") != "file" or not es_plantilla or nombre.lower() == "config.yml":
                continue
            archivo = pedir_json(entrada["url"], token)
            if not archivo or archivo.get("encoding") != "base64":
                continue
            texto = base64.b64decode(archivo["content"]).decode("utf-8", errors="replace")
            lineas |= lineas_de_plantilla(nombre, texto)
    return lineas


def quitar_plantilla(texto, lineas_plantilla):
    if not lineas_plantilla:
        return texto
    return "\n".join(
        linea for linea in (texto or "").splitlines()
        if normalizar(linea) not in lineas_plantilla
    )