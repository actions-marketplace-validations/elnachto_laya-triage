# Contributing to laya-triage

Thanks for your help! laya-triage is a GitHub Action that labels new issues with a fine-tuned Laya model running inside the Actions runner. Contributions of any size are welcome: code, tests, docs, translations, and reports of incorrect labels.

## Hacktoberfest

This project takes part in the spirit of Hacktoberfest 2026: learning and building with open-source AI and open-weight models. Issues labeled `good first issue` or `hacktoberfest` are a good place to start. Comment on the issue before you begin so two people don't work on the same thing. Low-effort pull requests (whitespace, renaming, adding your name) will be closed.

## Set up

You need Python 3.12.

```bash
python -m venv .venv
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements.txt
```

On Windows use `.venv\Scripts\python` instead of `.venv/bin/python`.

## Try your change

Perform the action on a sample issue. On GitHub no changes will be made unless LAYA_DRY_RUN is set to `LAYA_DRY_RUN=false`:

```bash
.venv/bin/python triage.py tests/eventos/issue_vago.json
```

In the first run the two models are downloaded (approximately 1.5 GB); then the template tests are carried out, even though the models are not required for them:

```bash
.venv/bin/python tests/probar_plantillas.py
```

## Where things are

| File | What it does |
|---|---|
| `triage.py` | Reads the event, cleans the issue body, runs the model and applies labels |
| `repo.py` | Reads the repository's labels and how common each issue type is |
| `plantillas.py` | Removes issue template text so only what the author wrote is classified |
| `preguntas.py` | The question the model answers for each issue |
| `modelos.py` | Downloads the pinned models from Hugging Face |
| `bench/` | Benchmarks behind every number in the README |
| `entrenamiento/` | Training and calibration scripts |

The majority of the names in the code are Spanish (`etiquetas` = labels, `cuerpo` = body, `mezcla` = mix). When you're adding new code, try to maintain the same style so that the project appears to be a single, unified whole, and don't include any comments; instead, explain the changes in your pull request.

## Pull requests

- Make sure that each pull request contains only a single change.
- Describe the corrections it makes and the way in which you tested it.
- If the results are affected, then include the benchmark command along with the numbers before and after.
- Never commit tokens, keys or files from `datos/` or `modelos/`.

## Wrong label?

When the action mistakenly labels an issue in your repository, you should open an issue including the title, the body (or a link to it), the label that was added, and the label that you expected. This kind of report provides the most useful data for the next model.