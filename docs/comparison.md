# laya-triage vs. alternatives

Working notes for the README. Figures as of September 2026.
Rule: only numbers a tool publishes itself, or numbers we measured on the same data. Anything else is "—".

## 1. Issue type classification

| Tool | Approach | Runs where | API key | Languages | Public benchmark | Reported result |
|---|---|---|---|---|---|---|
| **laya-triage** | Laya (fine-tuned) + calibration | Your runner | No | 100+ (14 measured) | Yes (this repo) | 85.1% acc. on NLBSE'23 validation · labels 91.5% of issues at 89.1% precision · **TODO: sealed test** |
| FastText (NLBSE'23 baseline) | fastText classifier | Research code | No | English | Yes | 85.1% |
| RoBERTa (NLBSE'23 best) | Fine-tuned transformer | Research code | No | English | Yes | 89.1% |
| GPT-4o fine-tuned (arXiv 2506.00128) | Fine-tuned LLM | OpenAI API | Yes (paid) | — | Yes | 85.66% F1 on NLBSE'24 (different dataset) |
| GPT-4o, no fine-tune (same paper) | Prompted LLM | OpenAI API | Yes (paid) | — | Yes | 65.47% F1 on NLBSE'24 |
| Ticket Tagger | fastText | Hosted GitHub App | No | English | — | — |
| Dosu | LLM | Hosted service | No (SaaS) | — | — | — (5,955+ repos) |
| github/ai-assessment-comment-labeler | LLM via GitHub Models | Your runner | No | — | — | — |
| jlowin/ai-labeler | LLM | Your runner | Yes (paid) | — | — | — |
| github/issue-labeler | Regex rules | Your runner | No | Rule-dependent | — | — |

### Issues opened in 2026 (never seen in training, 2,000 issues, 1,145 repos)

| Model | Macro F1 | Accuracy |
|---|---|---|
| Laya base | 0.523 | 56.4% |
| **laya-triage** | **0.688** | **70.2%** |

### Multilingual (same 500 issues machine-translated into 13 languages)

| Language | Laya base router | **laya-triage** |
|---|---|---|
| English | 89.2% | TODO |
| German | 74.6% | TODO |
| Portuguese | 74.0% | TODO |
| Spanish | 73.8% | TODO |
| Indonesian | 73.8% | TODO |
| French | 71.6% | TODO |
| Vietnamese | 71.2% | TODO |
| Russian | 70.8% | TODO |
| Turkish | 68.2% | TODO |
| Chinese | 68.2% | TODO |
| Japanese | 67.8% | TODO |
| Arabic | 67.4% | TODO |
| Hindi | 66.2% | TODO |
| Korean | 64.2% | TODO |

## 2. Pull request spam

Data: Hacktoberfest 2024–2025 PRs. Spam = labelled `spam` by a maintainer. Genuine = merged with `hacktoberfest-accepted`. Practice repos and bots excluded (448 spam, 849 genuine).

| Tool | Approach | Runs where | Public benchmark | Spam caught | Genuine PRs flagged |
|---|---|---|---|---|---|
| **laya-triage** | Laya + change summary | Your runner | Yes (this repo) | TODO | TODO |
| anti-slop (727★) | 34 configurable rules, account history | Your runner | — | — | — |
| Check and reject spam PRs | 3 rules, any one flags | Your runner | — | "single file" rule alone: 72.1%* | "single file" rule alone: **43.5%*** |
| Spamtoberfest (56★) | Community blocklist of users | Your runner | — | — | — |
| github/ai-moderator | LLM, issues and comments only | Your runner | — | Does not check PRs · archived Sep 2026 | — |

\* Our reimplementation of one published rule on our data, not the full tool.

## Measured so far, for the record

- Surface rules alone (title, empty body, one file, no deletions, few lines, text-only files): no combination flags fewer than 2% of genuine PRs. Best is all six rules together: catches 15.6% of spam and flags 3.3% of genuine PRs.
- `author_association` looks predictive, but it leaks: merged PRs turn their authors into contributors. We do not use it.
- `hacktoberfest-accepted` is not a quality label, and neither is `invalid` a spam label (52% of our "spam" set was `invalid`).