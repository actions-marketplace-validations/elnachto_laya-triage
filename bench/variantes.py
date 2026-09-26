from preguntas import TIPO

SIN_OTHER = {
    "type": "choice",
    "instructions": TIPO["instructions"],
    "criteria": {k: v for k, v in TIPO["criteria"].items() if k != "other"},
}

DESCRIPCIONES_V2 = {
    "type": "choice",
    "instructions": TIPO["instructions"],
    "criteria": {
        "bug": "something is broken: an error, crash, exception, wrong output or unexpected behavior in the existing software",
        "feature": "a request to add new functionality, change existing behavior, or improve performance, usability or design",
        "question": "the author asks for help, support or clarification on how to use, install or configure something, without reporting a defect",
        "docs": "the documentation, README, examples, code comments or website text is wrong, unclear or missing",
    },
}

INSTRUCCIONES_V2 = {
    "type": "choice",
    "instructions": "Classify this GitHub issue by what its author wants from the maintainers.",
    "criteria": DESCRIPCIONES_V2["criteria"],
}

VARIANTES = {
    "actual": TIPO,
    "sin_other": SIN_OTHER,
    "descripciones_v2": DESCRIPCIONES_V2,
    "instrucciones_v2": INSTRUCCIONES_V2,
}