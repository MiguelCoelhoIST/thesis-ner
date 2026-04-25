import spacy

baseline_model = spacy.load("models/baseline_model")
extended_model = spacy.load("models/eduardo_extended_model")

print("Baseline labels:", baseline_model.get_pipe("ner").labels)
print("Extended labels:", extended_model.get_pipe("ner").labels)