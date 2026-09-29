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

## Results

NLBSE'23 issue report classification. 5,000 issues sampled at random from the official test set, never used before, measured once after every decision was frozen on the validation split. ±0.9 points at 95%.

| System | Accuracy (= micro F1) | Macro F1 |
|---|---|---|
| RoBERTa, NLBSE'23 official baseline (full test set, trained on ~1.27M issues) | 89.1% | — |
| **laya-triage (this model + multilingual)** | **88.8%** | **0.779** |
| FastText, NLBSE'23 official baseline | 85.1% | — |
| Jev (TypeSafe, hosted), measured by us* | 84.4% | 0.704 |
| Laya base, same question* | 75.9% | — |
| harikarthikmanyam/laya-issue-triage, measured by us* | 64.5% | 0.547 |

\* Measured on a different random 5,000-issue sample of the same test set.

laya-triage is within the margin of error of the RoBERTa baseline while running on a free CPU runner. On the 4,807 test issues the router sends to this English model: 89.0% accuracy, macro F1 0.783.

Per class (whole system): bug 0.925 · feature 0.895 · question 0.602 · docs 0.696.

**Selective labeling.** With confidence ≥ 0.60 it labels 94.1% of issues at 91.1% precision and leaves the rest for a maintainer. On the validation split, a 0.95 threshold labels about half of the issues at 98% precision.

**Issues it has never seen.** 2,000 closed issues opened in 2026 across 1,145 repositories, 500 per class: macro F1 0.662, level with Jev (0.660) and far ahead of Laya base (0.523). This set is balanced on purpose, so it weighs questions four times more than a typical repository; with the natural class mix the same results correspond to about 84% accuracy.

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

This model was trained on the natural class mix of GitHub issues (bug 52.6%, feature 37.0%, question 5.9%, docs 4.4%), so it needs no class priors. If your repository receives a very different mix, for example mostly questions, multiply the probabilities by your own class frequencies divided by these and renormalize.

## Training

- Base: `convaiinnovations/laya` (English checkpoint, 421M parameters).
- Data: 1,000,000 issues from the NLBSE'23 training set at their natural class distribution; validation and test issues excluded.
- One epoch (12 hours on a single RTX 5070), AdamW, lr 2.5e-5 encoder / 1e-4 head, label smoothing 0.1, bf16.
- Issue bodies cleaned of template boilerplate and truncated to 1,500 characters.
- Calibration: temperature 0.737 fitted on half of the validation split (ECE 0.068 → 0.027). Label smoothing made the raw model underconfident; the temperature restores its confidence.
- Weights stored in bf16; predictions match the float32 checkpoint on the verification sample.

| Training issues | Validation accuracy |
|---|---|
| 150,000 (balanced, with priors) | 86.8% |
| 500,000 (natural mix) | 88.1% |
| 1,000,000 (natural mix) | 88.4% |

## Limitations

- **question** and **docs** are the hardest classes (F1 around 0.6 to 0.7). Many questions read like bug reports, and the model rarely predicts question because questions are rare in its training data.
- Issues written in 2026 are harder than the NLBSE'23 test set, which is older.
- Trained on English issues; non-English text should go to the multilingual model (the router does this automatically).
- Labels come from maintainers' GitHub labels, which are noisy: some issues are labeled inconsistently across projects.
- Not a spam or security classifier.

## Credits

Base model by [Convai Innovations](https://huggingface.co/convaiinnovations/laya) (Apache-2.0). Data from the [NLBSE'23 tool competition](https://github.com/nlbse2023/issue-report-classification). Built by [elnachto](https://github.com/elnachto).
