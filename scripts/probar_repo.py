import json
import sys
import urllib.request

from laya import Router

from preguntas import PREGUNTAS_ISSUE
from triage import decidir_issue

LIMITE_CUERPO = 1500


def obtener_issues(repo, cantidad):
    url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page={cantidad}"
    peticion = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "laya-triage"},
    )
    with urllib.request.urlopen(peticion) as respuesta:
        datos = json.load(respuesta)
    return [issue for issue in datos if "pull_request" not in issue]


def main():
    repo = sys.argv[1]
    cantidad = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    issues = obtener_issues(repo, cantidad)
    print(f"{len(issues)} issues descargados de {repo}")

    router = Router(default="multilingual")

    for issue in issues:
        cuerpo = (issue.get("body") or "")[:LIMITE_CUERPO]
        estado = {"title": issue["title"], "body": cuerpo}
        resultado = router.predict(estado, PREGUNTAS_ISSUE)
        etiquetas, comentario = decidir_issue(resultado["answers"])
        tipo = resultado["answers"]["tipo"]
        humanas = [etiqueta["name"] for etiqueta in issue["labels"]]

        print("=" * 70)
        print(f"#{issue['number']} {issue['title'][:80]}")
        print(f"laya:       {etiquetas}  ({tipo['choice']} {tipo['answer_confidence']:.2f})")
        print(f"humanos:    {humanas}")
        print(f"comentaría: {'sí' if comentario else 'no'}")


if __name__ == "__main__":
    main()