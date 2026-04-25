import spacy

print("spaCy version:", spacy.__version__)
# Load models
baseline_model = spacy.load("models/baseline_model")
extended_model = spacy.load("models/eduardo_extended_model")

text = """
A testemunha Susana Raquel Fernandes, residente na Rua do Sol, n.º 9, Funchal,
declarou em audiência de 11/11/2022.
"""

print("=== BASELINE MODEL ===")
doc1 = baseline_model(text)
for ent in doc1.ents:
    print(ent.text, ent.label_)

print("\n=== EXTENDED MODEL ===")
doc2 = extended_model(text)
for ent in doc2.ents:
    print(ent.text, ent.label_)