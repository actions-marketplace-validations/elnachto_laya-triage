<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/banner-dark.png">
    <img alt="laya-triage: free, local AI triage for GitHub issues and pull requests" src="docs/banner-light.png">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/elnachto/laya-triage/tags"><img alt="Version" src="https://img.shields.io/github/v/tag/elnachto/laya-triage?color=6B3FE7&label=version"></a>
  <img alt="License Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-16141F">
  <img alt="Runs in your runner" src="https://img.shields.io/badge/runs-in%20your%20runner-2E9E68">
  <img alt="No API key" src="https://img.shields.io/badge/API%20key-not%20needed-F2644B">
  <a href="https://huggingface.co/elnachto/laya-triage-en"><img alt="Models on Hugging Face" src="https://img.shields.io/badge/models-Hugging%20Face-6B3FE7"></a>
</p>



https://github.com/user-attachments/assets/a929519a-85ff-467b-9dc3-f49538046d64



Free, local AI triage for GitHub issues.

laya-triage is a GitHub Action that reads every new issue in your repository, labels it as a bug, feature request, question, or documentation problem, and asks for missing details. It runs a fine-tuned [Laya](https://github.com/NandhaKishorM/laya) model inside your GitHub Actions runner with no API key, no external service, and without sending issue text outside GitHub.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/exactitud-dark.png">
    <img alt="Accuracy on the NLBSE'23 issue classification test: RoBERTa baseline 89.1%, laya-triage 86.8%, FastText 85.1%, Jev 84.4%, Laya base 75.9%, laya-issue-triage 64.5%" src="docs/benchmarks/exactitud-light.png">
  </picture>
</p>

## What it does

| Event | Decision | Result |
|---|---|---|
| New issue | Type: bug, feature, question or docs | ![bug](https://img.shields.io/badge/bug-F2644B) ![enhancement](https://img.shields.io/badge/enhancement-2E9E68) ![question](https://img.shields.io/badge/question-6B3FE7) ![documentation](https://img.shields.io/badge/documentation-16141F) |
| New issue | Low confidence | ![needs-triage](https://img.shields.io/badge/needs--triage-9C98AE) for a human to review |
| New bug report | Key details are missing | ![needs-more-info](https://img.shields.io/badge/needs--more--info-6B3FE7) and a comment asking for steps, version and expected behavior |
| New pull request | Trivial change that looks like spam (experimental, off by default) | ![spam-probable](https://img.shields.io/badge/spam--probable-9C98AE) and a polite comment |

laya-triage never closes issues or pull requests. Maintainers keep full control over decisions.

## Quick start

Create `.github/workflows/triage.yml` in your repository:

```yaml
name: Triage

on:
  issues:
    types: [opened]

permissions:
  contents: read
  issues: write

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: elnachto/laya-triage@v1
```

The process starts in **dry-run mode**, showing its decisions in the workflow log without making changes. Open some issues and look at the logs. Once you're confident with the results, switch it on:

```yaml
      - uses: elnachto/laya-triage@v1
        with:
          dry-run: "false"
```

## Recommended: warm the model cache

The two models weigh about 1.5 GB. GitHub only lets trusted events like `schedule` and `workflow_dispatch` write to the cache. Issue runs can read it but not save it. Add this second workflow and run it once from the Actions tab:

```yaml
name: Warm Laya cache

on:
  workflow_dispatch:
  schedule:
    - cron: "17 6 * * 1,4"

permissions:
  contents: read

jobs:
  warm:
    runs-on: ubuntu-latest
    steps:
      - uses: elnachto/laya-triage@v1
        with:
          mode: warm-cache
```

GitHub removes caches that haven't been used for seven days, so it does so twice a week to keep the service running. Additionally, GitHub suspends any scheduled workflows after 60 days of inactivity in the repository; in that case, re-enable the workflow from the Actions tab.

On a typical runner, a triage run takes about 35 seconds with a warm cache.

## How it compares

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/cien-issues-dark.png">
    <img alt="Out of every 100 new issues: Laya base labels 51 right, 6 wrong and leaves 43; Jev 82 right, 13 wrong, 5 left; laya-triage 83 right, 9 wrong, 8 left for a maintainer" src="docs/benchmarks/cien-issues-light.png">
  </picture>
</p>

laya-triage only labels an issue when confident. It labels 91.7% of issues automatically, gets 90.2% of those right, and sends the rest to `needs-triage`, This results in fewer wrong labels than Jev (9 versus 13 per 100 issues)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/comparativa-dark.png">
    <img alt="Comparison of laya-triage with Jev, laya-issue-triage, the NLBSE'23 research baselines, ai-assessment-comment-labeler, ai-labeler, Dosu and issue-labeler on accuracy, cost, where issue text goes, API keys, languages and confidence" src="docs/benchmarks/comparativa-light.png">
  </picture>
</p>

Hosted triage costs money every month, and someone must keep paying for it. The original Issue-Label-Bot was archived in 2022 due to its infrastructure costs. laya-triage runs on the free minutes GitHub gives public repositories, so there is no service to shut down.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/idiomas-dark.png">
    <img alt="Accuracy in 14 languages: laya-triage between 84.0% and 90.6%, Jev between 83.8% and 88.2%, Laya base between 64.2% and 89.2%" src="docs/benchmarks/idiomas-light.png">
  </picture>
</p>

Issues in other languages go to a multilingual model. It matches a hosted API across 14 languages. On real non-English issues from 2026, its accuracy improved from 47.1% to 65.7% over the base model.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/confianza-dark.png">
    <img alt="Precision as the confidence threshold rises: fewer issues are labeled automatically and more are left for a maintainer, while precision grows to about 97%" src="docs/benchmarks/confianza-light.png">
  </picture>
</p>

The confidence is calibrated. When laya-triage says 90%, it is right about 90% of the time. A stricter threshold labels fewer issues with higher precision, reaching about 97% on half of them.

## Inputs

| Input | Default | Description |
|---|---|---|
| `dry-run` | `"true"` | Set to `"false"` to apply labels and comments |
| `mode` | `"triage"` | Use `"warm-cache"` to download the models and save them in the cache |
| `github-token` | `github.token` | Token used to add labels and comments |
| `spam-check` | `"false"` | Experimental. Set to `"true"` to check new pull requests for low-effort spam |

To try the spam check, also listen to pull requests and give the workflow write access to them:

```yaml
on:
  issues:
    types: [opened]
  pull_request_target:
    types: [opened]

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: elnachto/laya-triage@v1
        with:
          spam-check: "true"
```

## Optional: a bot with its own name

Labels and comments show up as `github-actions` by default. To use your own bot name instead:

1. Create a GitHub App with **Issues** and **Pull requests** set to *Read and write*, and the webhook disabled.
2. Install it on your repository.
3. Save its client ID as the variable `LAYA_APP_CLIENT_ID` and its private key as the secret `LAYA_APP_PRIVATE_KEY`.
4. Generate a token and pass it to the action:

```yaml
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.LAYA_APP_CLIENT_ID }}
          private-key: ${{ secrets.LAYA_APP_PRIVATE_KEY }}

      - uses: elnachto/laya-triage@v1
        with:
          dry-run: "false"
          github-token: ${{ steps.app-token.outputs.token }}
```

With a GitHub App token, the workflow only needs `contents: read`.

## How it runs

1. The action restores a Python environment and the two models from the GitHub cache.
2. It removes your repository's issue template boilerplate, so only what the author actually wrote is classified.
3. The Laya router sends English issues to [laya-triage-en](https://huggingface.co/elnachto/laya-triage-en) and other languages to [laya-triage-multilingual](https://huggingface.co/elnachto/laya-triage-multilingual). Both are downloaded at a fixed revision, so `@v1` always uses the exact models that were measured.
4. The model answers in a single forward pass on the runner's CPU. The answer is adjusted with class priors, because real repositories get far more bugs and feature requests than questions.
5. If the confidence is at least 0.60, the label is applied. Otherwise the issue gets `needs-triage`.

## Security

- The action never checks out pull request code. It only reads the title, description, and change stats from the event, which keeps `pull_request_target` safe with pull requests from forks.
- Issue and pull request text never reaches a shell. Python reads it from the event file, which prevents script injection.
- Only trusted events write to the model cache, as explained above, which protects against cache poisoning.
- Models are pinned to an exact commit on Hugging Face, so a new upload cannot change what an existing version of the action runs.

## Limitations

- **question** and **docs** are the hardest classes (F1 around 0.6). Many questions read like bug reports, and the class priors favor bug and feature. Repositories that receive mostly questions will see some of them labeled as bugs.
- The best published result on this benchmark is still the NLBSE'23 RoBERTa baseline (89.1%), trained on about 1.27M issues. laya-triage is 2.3 points behind while running on a free CPU runner.
- The multilingual model was trained on machine-translated issues.It is measured on 14 languages; other languages work through the base model but aren’t evaluated.
- The spam check is experimental: on our pull request data it catches only a small share of spam, which is why it is off by default.
- Bug reports with less than 30 characters of real content get `needs-more-info`. Very short but complete reports may also get this label.

## How it was measured

All numbers come from a random 5,000-issue sample of the official [NLBSE'23](https://github.com/nlbse2023/issue-report-classification) test set. It was used once, after every decision was frozen on a separate validation split. Jev and laya-issue-triage were run by us on the same sample with the same question. The ±0.9 point margin is the 95% interval for 5,000 issues.

To check that the models are not tuned to an old dataset, we also collected 2,000 closed issues opened in 2026 across 1,145 repositories:

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/issues-2026-dark.png">
    <img alt="Macro F1 on 2,000 real issues from 2026: laya-triage 0.725, Jev 0.660, Laya base 0.523" src="docs/benchmarks/issues-2026-light.png">
  </picture>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/benchmarks/curva-dark.png">
    <img alt="Validation accuracy while training the English model" src="docs/benchmarks/curva-light.png">
  </picture>
</p>

The scripts behind every number are in [`bench/`](bench) and [`entrenamiento/`](entrenamiento), and the raw results are in [`bench/resultados/`](bench/resultados). A longer write-up is in [docs/comparison.md](docs/comparison.md).

## Run it locally

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python triage.py tests/eventos/issue_vago.json
```

The first run downloads the two models (about 1.5 GB). Local runs never change anything on GitHub unless you set `LAYA_DRY_RUN=false` and a `GITHUB_TOKEN`.

## Credits

Built on [Laya](https://github.com/NandhaKishorM/laya) by Convai Innovations (Apache 2.0). Training and test data from the [NLBSE'23 tool competition](https://github.com/nlbse2023/issue-report-classification). Translations with [NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M).

## License

Apache 2.0. See [LICENSE](LICENSE).