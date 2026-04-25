## João vs Eduardo Contributions

### João (baseline work)
- Used BERTimbau for NER
- Implemented basic entity recognition
- Labels:
  - PER
  - ORG
  - LOC
  - DAT
- General-purpose NER for legal documents

### Eduardo (improvements)
1. Extended entity types:
   - Added IDP (identifiers)
   - Added MOR (addresses)

2. Improved semantic distinction:
   - Separated addresses (MOR) from locations (LOC)

3. Replaced rule-based detection:
   - IDPs previously detected with regex
   - Now learned by the model

4. Used synthetic data generation:
   - Generated annotated examples using GPT
   - Improved performance for low-frequency entities

### Overall impact
- More precise entity classification
- Better handling of legal-specific information
- More robust and scalable detection

## Manual comparison: baseline vs Eduardo extended model

A manual comparison was performed on 45 example sentences containing:
- people
- organizations
- locations
- dates
- addresses
- identifiers
- legal-role mentions (arguido, ré, testemunha, relator, etc.)

### Main observations

#### 1. Baseline model
The baseline model recognizes the original generic labels:
- PER
- ORG
- LOC
- DAT

However, it tends to classify full addresses as generic LOC and does not identify personal identifiers.

#### 2. Eduardo extended model
The extended model improves the baseline in two main ways:
- It distinguishes addresses/moradas from cities, using MOR for the address and LOC for the city.
- It detects IDP entities such as contract numbers, NIF, CC, IBAN, passport, and identification numbers.

#### 3. Remaining limitation
Even with these improvements, the extended model still does not recognize legal-specific semantic roles. Mentions such as:
- arguido
- réu/ré
- testemunha
- relator
- ofendida
- vítima
- autora
- denunciante

are still reduced to generic PER labels.

### Conclusion
The comparison confirms that Eduardo improved the inherited model mainly by:
- adding MOR/address recognition
- improving IDP detection
- making the NER output more semantically precise for these entity types

At the same time, the comparison also shows a clear next research direction:
extending the system to recognize more specialized legal-role entities instead of only generic person labels.