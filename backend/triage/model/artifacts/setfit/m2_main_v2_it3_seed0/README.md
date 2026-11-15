---
tags:
- setfit
- sentence-transformers
- text-classification
- generated_from_setfit_trainer
widget:
- text: The toes look grey and when I touch them it's like touching through a glove
- text: 'week 3 update: swelling down most mornings, sleeping 5-6 hours, walking to
    the end of the road with the frame. feeling more like myself'
- text: Coughed this morning and there were streaks of blood in what came up
- text: If I cut myself while on blood thinners, how long should I press on it?
- text: Hip is making click sound when doing exercises, no pain. Should I stop that
    exercise?
metrics:
- accuracy
pipeline_tag: text-classification
library_name: setfit
inference: true
---

# SetFit

This is a [SetFit](https://github.com/huggingface/setfit) model that can be used for Text Classification. A [LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) instance is used for classification.

The model has been trained using an efficient few-shot learning technique that involves:

1. Fine-tuning a [Sentence Transformer](https://www.sbert.net) with contrastive learning.
2. Training a classification head with features from the fine-tuned Sentence Transformer.

## Model Details

### Model Description
- **Model Type:** SetFit
<!-- - **Sentence Transformer:** [Unknown](https://huggingface.co/unknown) -->
- **Classification head:** a [LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) instance
- **Maximum Sequence Length:** 64 tokens
- **Number of Classes:** 3 classes
<!-- - **Training Dataset:** [Unknown](https://huggingface.co/datasets/unknown) -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Repository:** [SetFit on GitHub](https://github.com/huggingface/setfit)
- **Paper:** [Efficient Few-Shot Learning Without Prompts](https://arxiv.org/abs/2209.11055)
- **Blogpost:** [SetFit: Efficient Few-Shot Learning Without Prompts](https://huggingface.co/blog/setfit)

### Model Labels
| Label | Examples                                                                                                                                                                                                                                                                                                                                                |
|:------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 2     | <ul><li>'lips swelling up after the new antibiotic'</li><li>'After taking new tablet my face is swelling and eyes are puffy. Kindly advise urgent.'</li><li>"Mum took the first antibiotic tablet the hospital sent home with her about an hour ago, and now her lips are huge, her eyes are puffy and she's struggling to get her words out"</li></ul> |
| 1     | <ul><li>'Small itchy rash on my wrists since the new antibiotic, no swelling of face, breathing fine'</li><li>'Dad has an itchy patch on his back since the new pills, lips and face look normal'</li><li>'itchy spotty rash on my legs since tramadol, no swellin'</li></ul>                                                                           |
| 0     | <ul><li>'the skin under the plaster tape is itchy and a bit red, the rest of me is fine'</li><li>'What are the signs of an allergic reaction to antibiotics?'</li><li>'I am allergic to penicillin, kindly tell which painkillers are safe after hip surgery'</li></ul>                                                                                 |

## Uses

### Direct Use for Inference

First install the SetFit library:

```bash
pip install setfit
```

Then you can load this model and run inference.

```python
from setfit import SetFitModel

# Download from the 🤗 Hub
model = SetFitModel.from_pretrained("setfit_model_id")
# Run inference
preds = model("Coughed this morning and there were streaks of blood in what came up")
```

<!--
### Downstream Use

*List how someone could finetune this model on their own dataset.*
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Set Metrics
| Training set | Min | Median  | Max |
|:-------------|:----|:--------|:----|
| Word count   | 3   | 16.8536 | 39  |

| Label | Training Sample Count |
|:------|:----------------------|
| 0     | 632                   |
| 1     | 424                   |
| 2     | 577                   |

### Training Hyperparameters
- batch_size: (32, 32)
- num_epochs: (1, 1)
- max_steps: -1
- sampling_strategy: oversampling
- num_iterations: 3
- body_learning_rate: (2e-05, 2e-05)
- head_learning_rate: 0.01
- loss: CosineSimilarityLoss
- distance_metric: cosine_distance
- margin: 0.25
- end_to_end: False
- use_amp: False
- warmup_proportion: 0.1
- l2_weight: 0.01
- max_length: 64
- seed: 0
- eval_max_steps: -1
- load_best_model_at_end: False

### Training Results
| Epoch  | Step | Training Loss | Validation Loss |
|:------:|:----:|:-------------:|:---------------:|
| 0.0033 | 1    | 0.3233        | -               |

### Framework Versions
- Python: 3.11.9
- SetFit: 1.2.0
- Sentence Transformers: 6.0.1
- Transformers: 5.17.0
- PyTorch: 2.14.0+cpu
- Datasets: 5.2.0
- Tokenizers: 0.23.2

## Citation

### BibTeX
```bibtex
@article{https://doi.org/10.48550/arxiv.2209.11055,
    doi = {10.48550/ARXIV.2209.11055},
    url = {https://arxiv.org/abs/2209.11055},
    author = {Tunstall, Lewis and Reimers, Nils and Jo, Unso Eun Seo and Bates, Luke and Korat, Daniel and Wasserblat, Moshe and Pereg, Oren},
    keywords = {Computation and Language (cs.CL), FOS: Computer and information sciences, FOS: Computer and information sciences},
    title = {Efficient Few-Shot Learning Without Prompts},
    publisher = {arXiv},
    year = {2022},
    copyright = {Creative Commons Attribution 4.0 International}
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->