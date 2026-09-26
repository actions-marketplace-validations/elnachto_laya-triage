import json
import os
import sys

from laya import Router

from preguntas import PREGUNTAS_ISSUE, PREGUNTAS_PR

UMBRAL_TIPO = 0.60
UMBRAL_INFO = 0.75
UMBRAL_SPAM = 0.85

ETIQUETAS_TIPO = {
    "bug": "bug",
    "feature": "enhancement",
    "question": "question",
    "docs": "documentation",
    "other": "chore",
}

COMENTARIO_INFO = (
    "Thanks for opening this issue! It looks like some details are missing. "
    "Could you add the steps to reproduce, the version you are using and what you expected to happen?"
)

COMENTARIO_SPAM = (
    "This pull request looks like a very small change without a clear purpose. "
    "A maintainer will review it. If it is a real contribution, please describe what it fixes or improves."
)


def cargar_evento():
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_EVENT_PATH")
    if not ruta:
        sys.exit("No se encontró el evento: pasa una ruta o define GITHUB_EVENT_PATH")
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def decidir_issue(respuestas):
    etiquetas = []
    comentario = None

    tipo = respuestas["tipo"]
    if tipo["answer_confidence"] >= UMBRAL_TIPO:
        etiquetas.append(ETIQUETAS_TIPO[tipo["choice"]])
    else:
        etiquetas.append("needs-triage")

    if tipo["choice"] == "bug":
        info = respuestas["info_suficiente"]
        if info["choice"] == "B" and info["answer_confidence"] >= UMBRAL_INFO:
            etiquetas.append("needs-more-info")
            comentario = COMENTARIO_INFO

    return etiquetas, comentario


def es_cambio_trivial(pr):
    lineas = pr.get("additions", 0) + pr.get("deletions", 0)
    return pr.get("changed_files", 0) <= 1 and lineas <= 3


def decidir_pr(pr, respuestas):
    spam = respuestas["spam"]
    modelo_dice_spam = spam["choice"] == "B" and spam["answer_confidence"] >= UMBRAL_SPAM

    if modelo_dice_spam and es_cambio_trivial(pr):
        return ["spam-probable"], COMENTARIO_SPAM
    return [], None


def main():
    evento = cargar_evento()
    router = Router(default="multilingual")

    if "pull_request" in evento:
        item = evento["pull_request"]
        estado = {"title": item["title"], "body": item.get("body") or ""}
        resultado = router.predict(estado, PREGUNTAS_PR)
        etiquetas, comentario = decidir_pr(item, resultado["answers"])
        tipo_item = "pull_request"
    elif "issue" in evento:
        item = evento["issue"]
        estado = {"title": item["title"], "body": item.get("body") or ""}
        resultado = router.predict(estado, PREGUNTAS_ISSUE)
        etiquetas, comentario = decidir_issue(resultado["answers"])
        tipo_item = "issue"
    else:
        sys.exit("Evento no soportado: solo issues y pull requests")

    resumen = {
        "tipo": tipo_item,
        "numero": item["number"],
        "titulo": item["title"],
        "modelo": resultado["routing"]["model"],
        "etiquetas": etiquetas,
        "comentario": comentario,
        "confianzas": {
            nombre: {"choice": r["choice"], "answer_confidence": r["answer_confidence"]}
            for nombre, r in resultado["answers"].items()
        },
    }
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()