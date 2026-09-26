# laya-triage

Free, local AI triage solution for GitHub issues and pull requests.

laya-triage is a GitHub Action that reads every new issue and pull request in your repos, labels them, requests missing details, and flags low-effort and spam content. It runs the [Laya](https://github.com/NandhaKishorM/laya) decision model inside your GitHub Actions runner: no API key, no external service, and nothing leaves GitHub.

## What it does

| Event | Decision | Result |
|---|---|---|
| New issue | Type: bug, feature, question, docs or other | Adds `bug`, `enhancement`, `question`, `documentation` or `chore` |
| New issue | Low confidence | Adds `needs-triage` for a human to review |
| New bug report | Key details are missing | Adds `needs-more-info` and asks for steps, version and expected behavior |
| New pull request | Trivial change that looks like spam | Adds `spam-probable` and leaves a polite comment |

laya-triage does not close issues or pull requests. Maintainers keep full control over decisions.

## Quick start

Create `.github/workflows/triage.yml` file in your repository:

```yaml
name: Triage

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
```

The action starts in **dry-run mode**, printing its decisions in the workflow log without changing anything. Open a few issues, read the logs, and when you trust the results, turn it on:

```yaml
      - uses: elnachto/laya-triage@v1
        with:
          dry-run: "false"
```

## Recommended: warm the model cache

The Laya models are about 1.37 GB; GitHub permits only trusted events such as `schedule` and `workflow_dispatch` to write to the cache, so issue and pull request runs can read it but not save it. Therefore, add this second workflow and run it once from the Actions tab:

```yaml
name: Warm Laya cache

on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * 1"

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

The weekly schedule keeps the cache active, since GitHub deletes any cache not used for seven days.

## Inputs

| Input | Default | Description |
|---|---|---|
| `dry-run` | `"true"` | Set to `"false"` to apply labels and comments |
| `mode` | `"triage"` | Use `"warm-cache"` to download the models and save them in the cache |
| `github-token` | `github.token` | Token used to add labels and comments |

## Optional: a bot with its own name

Labels and comments show up as `github-actions` by default. If you want to use your own bot name instead, then:

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

## Security

- The action never checks out pull request code. It only reads the title, description, and change stats from the event, making `pull_request_target` safe to use with pull requests from forks.
- Issue and pull request text never reaches a shell. Python reads it from the event file to prevent script injection.
- Only trusted events write to the model cache, as explained above, which protects against cache poisoning.

## Limitations

- laya-triage uses the **base** Laya checkpoints, which are not fine-tuned for GitHub triage yet. Treat its labels as suggestions.
- Confidence thresholds are provisional. In a small test on 25 real issues from `microsoft/vscode` and `facebook/react`, no issue received a wrong type label, and uncertain issues went to `needs-triage`. A larger evaluation is planned.
- Issue templates can make empty reports look complete to the model.
- Each run takes about one minute on a standard runner, mostly spent installing dependencies.

## Run it locally

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python triage.py tests/eventos/issue_vago.json
```

Local runs always run in dry-run mode.

## Credits

Built on [Laya](https://github.com/NandhaKishorM/laya) by Convai Innovations and released under Apache 2.0.

## License

Apache 2.0. See [LICENSE](LICENSE).