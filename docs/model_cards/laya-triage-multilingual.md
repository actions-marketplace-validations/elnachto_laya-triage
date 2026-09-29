---
license: apache-2.0
base_model: convaiinnovations/laya-multilingual
language:
- multilingual
- en
- de
- es
- pt
- fr
- id
- vi
- ru
- tr
- zh
- ja
- ko
- ar
- hi
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

# laya-triage-multilingual

Classifies GitHub issues written in any language as **bug**, **feature**, **question** or **docs**. A fine-tune of [Laya multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) (mmBERT-base) used by the [laya-triage](https://github.com/elnachto/laya-triage) GitHub Action for non-English issues, next to the English model [laya-triage-en](https://huggingface.co/elnachto/laya-triage-en).

## Results

The same 500 NLBSE'23 validation issues, machine-translated with NLLB-200 into 13 languages. Accuracy (±3 points per language):

| Language | Laya base | Jev (TypeSafe, hosted) | **laya-triage** |
|---|---|---|---|
| English | 89.2% | 88.2% | **90.6%** |
| German | 74.6% | 85.8% | **87.4%** |
| Vietnamese | 71.2% | 84.4% | **86.6%** |
| Chinese | 68.2% | 83.8% | **86.2%** |
| Japanese | 67.8% | 84.4% | **86.0%** |
| Turkish | 68.2% | 85.0% | **85.8%** |
| Indonesian | 73.8% | 86.0% | 85.6% |
| Spanish | 73.8% | 85.6% | 85.2% |
| Hindi | 66.2% | 85.4% | 85.0% |
| Portuguese | 74.0% | 86.6% | 84.8% |
| Russian | 70.8% | 85.8% | 84.6% |
| Korean | 64.2% | 83.8% | **84.4%** |
| French | 71.6% | 85.2% | 84.2% |
| Arabic | 67.4% | 84.8% | 84.0% |

laya-triage and Jev are within noise of each other across languages; both are far ahead of the untuned base.

Translations can flatter a model trained on translations, so we also checked real issues: on 367 non-English issues opened in 2026 (never seen, written by people, not translated) accuracy went from **47.1% to 65.7%** without class priors, and to 61.0% with the priors the action applies. That set is balanced on purpose, which penalizes priors; on typical repositories the priors help.

## How to use

Use it through the Laya router together with the English model, with the exact training question. See [laya-triage-en](https://huggingface.co/elnachto/laya-triage-en#how-to-use) for the code; this checkpoint is the `"multilingual"` entry.

## Training

- Base: `convaiinnovations/laya-multilingual` (mmBERT-base, 322M parameters).
- Data: 2,000 NLBSE'23 training issues (500 per class) translated into 13 languages with NLLB-200 distilled 600M, plus the English originals and 10,000 extra English issues: 35,200 examples. Code blocks, stack traces and error messages were left untranslated, as in real issues.
- Validation: 200 issues held out in all 14 languages (no issue appears in both splits in any language).
- One epoch, same recipe as the English model; the second epoch overfit and was discarded.
- Calibration: temperature 1.203 (the base model was overconfident), ECE 0.077 → 0.053.

## Limitations

- Machine-translated training data: real issues mix languages, code and English error messages more than translations do.
- 13 languages measured; others are supported by the base model but not evaluated.
- Trained on balanced classes, so it expects class priors: multiply the probabilities by the priors stored in `rl_agent_config.json` (`laya_triage.priores`: bug 0.526, feature 0.370, question 0.060, docs 0.044) and renormalize, as the action does.

## Credits

Base model by [Convai Innovations](https://huggingface.co/convaiinnovations/laya-multilingual) (Apache-2.0). Translation with [NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M). Data from the [NLBSE'23 tool competition](https://github.com/nlbse2023/issue-report-classification). Built by [elnachto](https://github.com/elnachto).
