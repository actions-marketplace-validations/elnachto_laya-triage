---
license: apache-2.0
base_model: convaiinnovations/laya
language:
- en
tags:
- laya
- github
- issue-triage
- text-classification
- calibrated-decisions
metrics:
- accuracy
- f1
---

# laya-triage-en

Classifies GitHub issues as **bug**, **feature**, **question** or **docs**. A fine-tune of [Laya](https://huggingface.co/convaiinnovations/laya) (ModernBERT-large, English checkpoint) that powers the [laya-triage](https://github.com/elnachto/laya-triage) GitHub Action, together with its multilingual sibling [laya-triage-multilingual](https://huggingface.co/elnachto/laya-triage-multilingual).

Runs in a single forward pass on CPU or GPU. No API key, no text generation, and the confidence is calibrated, so a caller can abstain when it is unsure.

This is the v1.1 model. It was trained from scratch on the 1M NLBSE'23 issues of v1.0 plus 127,140 recent issues from active repositories, so it keeps its NLBSE'23 accuracy and handles today's issues better.

## Results

### Recent issues from active repositories

10,026 closed issues opened in 2025 and 2026 in 288 repositories with at least 1,000 stars. Labels were applied by a maintainer, not by the author or an issue template, and no repository in this set was used for training. Measured once, after every decision was frozen on a separate validation split. Class priors estimated per repository from its other labeled issues, as the action's `class-priors: auto` does.

| System | Accuracy | Macro F1 |
|---|---|---|
| **laya-triage v1.1 (this model + multilingual)** | **82.3%** | **0.742** |
| laya-triage v1.0 | 79.8% | 0.690 |
| Jev (TypeSafe, hosted), measured by us | 78.1% | 0.660 |
| Always bug | 57.6% | — |

Per class: bug 0.884 · feature 0.786 · question 0.649 · docs 0.650. It recognizes 58.3% of questions, against 43.7% for v1.0 and 29.6% for Jev.

With confidence ≥ 0.60 it labels 88.8% of issues at 86.3% precision: per 100 issues, 77 labeled right, 12 wrong and 11 left for a maintainer (Jev: 77, 20 and 3; v1.0: 77, 17 and 6).

### NLBSE'23 issue report classification

5,000 issues sampled at random from the official test set, never used before, measured once. ±0.9 points at 95%.

| System | Accuracy (= micro F1) | Macro F1 |
|---|---|---|
| RoBERTa, NLBSE'23 official baseline (full test set, trained on ~1.27M issues) | 89.1% | — |
| **laya-triage v1.1 (this model + multilingual)** | **88.8%** | **0.781** |
| laya-triage v1.0 | 88.8% | 0.779 |
| FastText, NLBSE'23 official baseline | 85.1% | — |
| Jev (TypeSafe, hosted), measured by us* | 84.4% | 0.704 |
| Laya base, same question* | 75.9% | — |
| harikarthikmanyam/laya-issue-triage, measured by us* | 64.5% | 0.547 |

\* Measured on a different random 5,000-issue sample of the same test set.

On the 4,807 test issues the router sends to this English model: 89.0% accuracy, macro F1 0.784. Per class (whole system): bug 0.924 · feature 0.898 · question 0.616 · docs 0.686. With confidence ≥ 0.60 it labels 91.0% of issues at 92.3% precision. On the validation split, a 0.85 threshold labels 60% of issues at 97.9% precision.

### Issues opened in 2026

2,000 closed issues opened in 2026 across 1,145 repositories, 500 per class. The set is balanced on purpose, so it weighs questions four times more than a typical repository. With class priors set to that mix: accuracy 76.9%, macro F1 0.758 (v1.0: 0.734; Jev without priors: 0.660; Laya base: 0.523).

## How to use

The answer only matches the reported numbers when the question is exactly the one used in training:

```python
from laya import Router

QUESTION = {
    "type": "choice",
    "instructions": "What kind of GitHub issue is this?",
    "criteria": {
        "bug": "something is broken, crashes, shows errors or behaves wrongly",
        "feature": "a request for new functionality or an improvement",
        "question": "the user asks for help, how to use, install or configure something",
        "docs": "the user reports an error, typo or missing section in the existing documentation",
    },
}

router = Router(
    default="multilingual",
    models={"english": "elnachto/laya-triage-en", "multilingual": "elnachto/laya-triage-multilingual"},
)
result = router.predict({"title": "App crashes on save", "body": "Stack trace attached..."}, {"type": QUESTION})
answer = result["answers"]["type"]
print(answer["choice"], answer["answer_confidence"])
```

### Class balance

This model was trained on bug 52.5%, feature 35.2%, question 7.8% and docs 4.6%, close to the natural mix of GitHub issues, so it needs no class priors. The mix is stored in `rl_agent_config.json` under `laya_triage.mezcla_base`. If your repository receives a very different mix, for example mostly questions, multiply the probabilities by your own class frequencies divided by these and renormalize. The action does this automatically with `class-priors: auto`.

## Training

- Base: `convaiinnovations/laya` (English checkpoint, 421M parameters), trained from scratch rather than from v1.0.
- Data: 1,254,280 rows. The 1,000,000 NLBSE'23 training issues of v1.0, plus 127,140 recent issues from active repositories with 200+ stars, labeled by a maintainer, repeated twice. Repositories used for validation and testing were excluded.
- One epoch (15.5 hours on a single RTX 5070), AdamW with linear warmup and decay, lr 2.5e-5 encoder / 1e-4 head, label smoothing 0.1, bf16.
- Issue bodies cleaned of template boilerplate and truncated to 1,500 characters.
- Calibration: temperature 0.966 fitted on half of a validation split of recent issues from repositories never seen in training (ECE 0.034).
- Weights stored in bf16; predictions match the float32 checkpoint on the verification sample.

| Model | NLBSE'23 test | Recent issues |
|---|---|---|
| Laya base | 75.9% | — |
| 150,000 issues (balanced, with priors) | 87.2% | — |
| v1.0: 1,000,000 issues (natural mix) | 88.8% | 79.8% |
| v1.0 fine-tuned on recent issues (discarded) | 87.9% | 81.9% |
| **v1.1: 1M + recent issues, from scratch** | **88.8%** | **82.3%** |

Fine-tuning v1.0 on recent issues improved them but cost almost a point on NLBSE'23, so v1.1 was trained on both from the start.

## Limitations

- **question** and **docs** are the hardest classes (F1 around 0.6 to 0.7). Many questions read like bug reports, and questions are rare in real repositories.
- Trained on English issues; non-English text should go to the multilingual model (the router does this automatically).
- Labels come from maintainers' GitHub labels, which are noisy: some issues are labeled inconsistently across projects.
- Not a spam or security classifier.

## Credits

Base model by [Convai Innovations](https://huggingface.co/convaiinnovations/laya) (Apache-2.0). Data from the [NLBSE'23 tool competition](https://github.com/nlbse2023/issue-report-classification) and public GitHub issues. Built by [elnachto](https://github.com/elnachto).
