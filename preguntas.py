TIPO = {
    "type": "choice",
    "instructions": "What kind of GitHub issue is this?",
    "criteria": {
        "bug": "something is broken, crashes, shows errors or behaves wrongly",
        "feature": "a request for new functionality or an improvement",
        "question": "the user asks for help, how to use, install or configure something",
        "docs": "the user reports an error, typo or missing section in the existing documentation",
    },
}

INFO_SUFICIENTE = {
    "type": "choice",
    "instructions": "Does the issue include enough information to reproduce or act on it?",
    "criteria": {
        "A": "yes, it has clear steps, versions or context",
        "B": "no, key details are missing",
    },
}

SPAM = {
    "type": "choice",
    "instructions": "Is this a genuine contribution or low-effort spam?",
    "criteria": {
        "A": "a genuine report or contribution",
        "B": "low-effort spam, like adding a name or a trivial meaningless change",
    },
}

PREGUNTAS_ISSUE = {"tipo": TIPO}
PREGUNTAS_PR = {"spam": SPAM}