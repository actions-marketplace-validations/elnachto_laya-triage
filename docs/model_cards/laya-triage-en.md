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

NLBSE'23 issue report classification, random 5,000-issue sample of the official test set, measured once after every decision was frozen on the validation split. ±0.9 points at 95%.

| System | Accuracy (= micro F1) | Macro F1 |
|---|---|---|
| RoBERTa, NLBSE'23 official baseline (trained on ~1.27M issues) | 89.1% | — |
| **laya-triage (this model + multilingual, with class priors)** | **86.8%** | **0.756** |
| FastText, NLBSE'23 official baseline | 85.1% | — |
| Jev (TypeSafe, hosted), measured by us | 84.4% | 0.704 |
| Laya base, same question | 75.9% | — |
| harikarthikmanyam/laya-issue-triage, measured by us | 64.5% | 0.547 |

On the 4,775 test issues the router sends to this English model: 87.0% accuracy, macro F1 0.759.

Per class (whole system): bug 0.907 · feature 0.879 · question 0.595 · docs 0.642.

**Selective labeling.** With confidence ≥ 0.60 it labels 91.7% of issues at 90.2% precision and leaves the rest for a maintainer. Stricter thresholds reach ~97% precision on about half of the issues.

**Issues it has never seen.** 2,000 closed issues opened in 2026 across 1,145 repositories (500 per class): macro F1 0.725 vs 0.523 for Laya base and 0.660 for Jev.

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

### Class priors

The model was trained on balanced classes. Real repositories are not balanced, so the reported numbers multiply the probabilities by the class priors stored in `rl_agent_config.json` (`laya_triage.priores`: bug 0.526, feature 0.370, question 0.060, docs 0.044) and renormalize. If your repository has a very different mix (for example many questions), skip the priors or use your own.

## Training

- Base: `convaiinnovations/laya` (English checkpoint, 421M parameters).
- Data: 150,000 issues from the NLBSE'23 training set, 37,500 per class; validation and test issues excluded.
- One epoch, AdamW, lr 2.5e-5 encoder / 1e-4 head, label smoothing 0.1, bf16 on a single RTX 5070. The second epoch overfit and was discarded.
- Issue bodies cleaned of template boilerplate and truncated to 1,500 characters.
- Calibration: temperature 0.741 fitted on half of the validation split (ECE 0.083 → 0.022 with priors).
- Weights stored in bf16; predictions match the float32 checkpoint on the verification sample.

## Limitations

- **question** and **docs** are the hardest classes (F1 ≈ 0.6). Many "questions" read like bug reports.
- Trained on English issues; non-English text should go to the multilingual model (the router does this automatically).
- Labels come from maintainers' GitHub labels, which are noisy: some issues are labeled inconsistently across projects.
- Not a spam or security classifier.

## Credits

Base model by [Convai Innovations](https://huggingface.co/convaiinnovations/laya) (Apache-2.0). Data from the [NLBSE'23 tool competition](https://github.com/nlbse2023/issue-report-classification). Built by [elnachto](https://github.com/elnachto).
