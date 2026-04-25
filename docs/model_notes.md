# Model Notes

## Inherited models

### Baseline model
Path:
- `models/baseline_model/`

Description:
- baseline model previously used before Eduardo's improvements
- baseline_model → iris-lfs-storage/model-gpt/model-best

### Eduardo extended model
Path:
- `models/eduardo_extended_model/`

Description:
- improved model trained by Eduardo
- appears to better distinguish address/morada entities
- eduardo_extended_model → iris-lfs-storage/model-extended

## Initial comparison

Test sentence:

> A testemunha Susana Raquel Fernandes, residente na Rua do Sol, n.º 9, Funchal, declarou em audiência de 11/11/2022.

### Baseline output
- `Susana Raquel Fernandes` → `PER`
- `Rua do Sol, n.º 9, Funchal` → `LOC`
- `11/11/2022` → `DAT`

### Extended output
- `Susana Raquel Fernandes` → `PER`
- `Rua do Sol, n.º 9` → `MOR`
- `Funchal` → `LOC`
- `11/11/2022` → `DAT`

## Interpretation

The extended model seems to improve over the baseline by:
- separating the address from the city
- labeling the address as `MOR`

This suggests that Eduardo’s work extended the model to recognize more specific address-like entities.

## Technical note

When loading the inherited models, compatibility warnings appear because:
- the models were trained with older spaCy / transformers versions
- current environment uses newer versions

For now the models still load and run, but this should be kept in mind when evaluating results.

Label mismatch problem:

Dataset: ADDR
Model:   MOR

You MUST fix or standardize this later.

## Model Evolution

### João (baseline)
- Basic NER model
- Labels: PER, ORG, LOC, DAT

### Eduardo (extended model)
- Added IDP and MOR entities
- Improved distinction between address and location
- Replaced regex-based ID detection with ML
- Used synthetic data generation (GPT) to improve performance

### Current direction (Miguel)
- Extend model to recognize legal roles:
  - Arguido
  - Réu
  - Testemunha
  - Relator
- Explore better data generation strategies
- Possibly test alternative transformer models