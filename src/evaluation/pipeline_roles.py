import json
from pathlib import Path

import spacy
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression


DATASET_PATH = Path("data/processed/roles_v1.jsonl")
NER_MODEL_PATH = "models/eduardo_extended_model"


def load_role_dataset(path: Path):
    texts = []
    labels = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            texts.append(record["text"])
            labels.append(record["label"])

    return texts, labels


def train_role_classifier():
    texts, labels = load_role_dataset(DATASET_PATH)

    vectorizer = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    X = vectorizer.fit_transform(texts)

    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(X, labels)

    return vectorizer, classifier


def main():
    print("Loading Eduardo NER model...")
    nlp = spacy.load(NER_MODEL_PATH)

    print("Training role classifier...")
    vectorizer, role_classifier = train_role_classifier()

    test_texts = [
        "O arguido João Martins foi ouvido em tribunal.",
        "A testemunha Ana Silva prestou declarações.",
        "O relator Carlos Mendes proferiu o acórdão.",
        "O réu Pedro Costa foi condenado.",
        "Maria Ferreira reside na Rua das Flores, Lisboa.",
        "O arguido Paulo Rocha reside na Praceta das Oliveiras, n.º 7, Faro.",
    ]

    for text in test_texts:
        print("\n==============================")
        print("TEXT:", text)

        doc = nlp(text)

        if not doc.ents:
            print("No entities found.")
            continue

        for ent in doc.ents:
            if ent.label_ == "PER":
                X_test = vectorizer.transform([text])
                role = role_classifier.predict(X_test)[0]
                if role == "UNKNOWN":
                    print(f"{ent.text} -> PER")
                else:
                    print(f"{ent.text} -> PER -> {role}")
            else:
                print(f"{ent.text} -> {ent.label_}")


if __name__ == "__main__":
    main()