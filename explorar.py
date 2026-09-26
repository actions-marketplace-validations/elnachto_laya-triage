import json
import time
from laya import Router

router = Router(default="multilingual")

preguntas = {
    "tipo": {
        "type": "choice",
        "instructions": "What kind of GitHub issue is this?",
        "criteria": {
            "bug": "something is broken, crashes, shows errors or behaves wrongly",
            "feature": "a request for new functionality or an improvement",
            "question": "the user asks for help, how to use, install or configure something",
            "docs": "the user reports an error, typo or missing section in the existing documentation",
        },
    },
    "urgencia": {
        "type": "score",
        "instructions": "How urgent is this issue for the maintainers?",
        "criteria": [
            "low, it can wait",
            "normal",
            "high, it affects many users",
            "critical, data loss or security problem",
        ],
    },
    "info_suficiente": {
        "type": "choice",
        "instructions": "Does the issue include enough information to reproduce or act on it?",
        "criteria": {
            "A": "yes, it has clear steps, versions or context",
            "B": "no, key details are missing",
        },
    },
    "spam": {
        "type": "choice",
        "instructions": "Is this a genuine contribution or low-effort spam?",
        "criteria": {
            "A": "a genuine report or contribution",
            "B": "low-effort spam, like adding a name or a trivial meaningless change",
        },
    },
}

issues = [
    {
        "title": "App crashes when uploading a photo on Android 14",
        "body": "Steps: 1) open profile 2) tap upload 3) pick any jpg. The app closes instantly. Version 2.3.1, Pixel 7. Logcat attached.",
    },
    {
        "title": "doesnt work",
        "body": "it doesnt work pls fix",
    },
    {
        "title": "Add dark mode",
        "body": "It would be great to have a dark theme option in settings.",
    },
    {
        "title": "¿Cómo configuro la base de datos?",
        "body": "No entiendo cómo conectar PostgreSQL, ¿hay algún ejemplo?",
    },
    {
        "title": "Update README.md",
        "body": "added my name to the readme for hacktoberfest",
    },
]

for issue in issues:
    inicio = time.perf_counter()
    resultado = router.predict(issue, preguntas)
    ms = (time.perf_counter() - inicio) * 1000
    print("=" * 70)
    print(issue["title"])
    print(f"modelo: {resultado['routing']['model']} | {ms:.0f} ms")
    print(json.dumps(resultado["answers"], indent=2, ensure_ascii=False))