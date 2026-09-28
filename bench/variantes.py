from preguntas import TIPO

CON_OTHER = {
    "type": "choice",
    "instructions": TIPO["instructions"],
    "criteria": {
        **TIPO["criteria"],
        "other": "internal tasks like refactoring, cleanup, tests or dependency updates",
    },
}

VARIANTES = {
    "actual": CON_OTHER,
    "sin_other": TIPO,
}