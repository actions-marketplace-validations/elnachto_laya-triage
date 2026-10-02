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

This is the v1.1 model: the v1.0 multilingual model, fine-tuned on real recent issues from active repositories.

## Results

### Real non-English issues

Issues written by people, not translated, that the router sent to this model. No repository in these sets was used for training.

| Set | v1.0 | **v1.1** |
|---|---|---|
| Recent issues from 288 active repositories (1,031 routed here), adapted to each repository | 74.0% | **77.6%** |
| Issues opened in 2026 (367 routed here), priors set to the set's balanced mix | 65.7% | **71.1%** |

### 14 languages

The same 500 NLBSE'23 validation issues, machine-translated with NLLB-200. Accuracy of the whole system (router + both models) with the natural class mix, ±3 points per language:

| Language | Laya base | Jev (TypeSafe, hosted) | laya-triage v1.0 | **laya-triage v1.1** |
|---|---|---|---|---|
| English | 89.2% | 88.2% | 90.6% | **92.4%** |
| Vietnamese | 71.2% | 84.4% | 86.6% | **87.6%** |
| German | 74.6% | 85.8% | 87.4% | **86.4%** |
| Turkish | 68.2% | 85.0% | 85.8% | **86.4%** |
| Portuguese | 74.0% | 86.6% | 84.8% | 86.4% |
| Indonesian | 73.8% | 86.0% | 85.6% | **86.2%** |
| Spanish | 73.8% | 85.6% | 85.2% | **86.2%** |
| Russian | 70.8% | 85.8% | 84.6% | 85.6% |
| French | 71.6% | 85.2% | 84.2% | **85.4%** |
| Hindi | 66.2% | 85.4% | 85.0% | 85.2% |
| Arabic | 67.4% | 84.8% | 84.0% | **85.0%** |
| Chinese | 68.2% | 83.8% | 86.2% | **84.8%** |
| Japanese | 67.8% | 84.4% | 86.0% | **84.8%** |
| Korean | 64.2% | 83.8% | 84.4% | **84.8%** |

v1.1 is ahead of Jev in 11 of 14 languages (in bold); most gaps between the two are within noise. Average over the 13 non-English languages: 85.8% for v1.1, 85.4% for v1.0 and 85.1% for Jev.

## How to use

Use it through the Laya router together with the English model, with the exact training question. See [laya-triage-en](https://huggingface.co/elnachto/laya-triage-en#how-to-use) for the code; this checkpoint is the `"multilingual"` entry.

### Class balance

v1.1 was trained on bug 53.2%, feature 30.8%, question 11.0% and docs 5.0%. The mix is stored in `rl_agent_config.json` under `laya_triage.mezcla_base`. To match a repository's own mix, multiply the probabilities by your class frequencies divided by these and renormalize. The action does this automatically with `class-priors`.

## Training

- Base: `convaiinnovations/laya-multilingual` (mmBERT-base, 322M parameters).
- v1.0: 2,000 NLBSE'23 training issues (500 per class) translated into 13 languages with NLLB-200 distilled 600M, plus the English originals and 10,000 extra English issues: 35,200 examples. Code blocks, stack traces and error messages were left untranslated, as in real issues.
- v1.1: v1.0 fine-tuned on 97,593 issues, 47,593 recent issues from active repositories labeled by a maintainer plus 50,000 NLBSE'23 issues so it keeps what it already knew. Repositories used for validation and testing were excluded. Validation accuracy on recent issues from unseen repositories went from 65.1% to 72.2%.
- Same recipe as the English model: AdamW, lr 2.5e-5 encoder / 1e-4 head, label smoothing 0.1, bf16.
- Calibration: temperature 1.013, ECE 0.037 on recent validation issues.

## Limitations

- Most non-English issues in real repositories are in Chinese; the other languages are measured mainly on translations, which are cleaner than real issues that mix languages, code and English error messages.
- 14 languages measured; others are supported by the base model but not evaluated.
- **question** and **docs** remain the hardest classes, as in the English model.

## Credits

Base model by [Convai Innovations](https://huggingface.co/convaiinnovations/laya-multilingual) (Apache-2.0). Translation with [NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M). Data from the [NLBSE'23 tool competition](https://github.com/nlbse2023/issue-report-classification) and public GitHub issues. Built by [elnachto](https://github.com/elnachto).
