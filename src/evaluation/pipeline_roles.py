import spacy
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
import json

# Load NER model
nlp = spacy.load("models/eduardo_extended_model")

# Load role classifier (retrain quickly here)
texts = []
labels = []

with open("data/processed/roles_v1.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        texts.append(data["text"])
        labels.append(data["label"])

vectorizer = CountVectorizer()
X = vectorizer.fit_transform(texts)

clf = LogisticRegression(max_iter=1000)
clf.fit(X, labels)

# Test full pipeline
text = "O arguido João Martins foi ouvido em tribunal."

doc = nlp(text)

print("TEXT:", text)

for ent in doc.ents:
    if ent.label_ == "PER":
        X_test = vectorizer.transform([text])
        role = clf.predict(X_test)[0]
        print(f"{ent.text} -> PER -> {role}")
    else:
        print(f"{ent.text} -> {ent.label_}")