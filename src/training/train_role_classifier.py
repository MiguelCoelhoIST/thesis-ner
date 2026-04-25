import json
from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression


DATASET_PATH = Path("data/processed/roles_v1.jsonl")


def load_dataset(path):
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


def main():
    print("Loading dataset...")

    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    texts, labels = load_dataset(DATASET_PATH)

    print(f"Loaded examples: {len(texts)}")
    print(f"Labels: {sorted(set(labels))}")

    print("\nTraining classifier...")

    vectorizer = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    X = vectorizer.fit_transform(texts)

    model = LogisticRegression(max_iter=1000)
    model.fit(X, labels)

    print("Training complete!")

    test_sentences = [
        "O arguido Rui Lopes foi condenado.",
        "A testemunha Carla Mendes declarou em tribunal.",
        "O relator João Costa decidiu o processo.",
        "O réu Manuel Ferreira apresentou contestação.",
        "Maria Ferreira reside na Rua das Flores, Lisboa.",
    ]

    print("\nPredictions:")
    X_test = vectorizer.transform(test_sentences)
    predictions = model.predict(X_test)

    for text, pred in zip(test_sentences, predictions):
        print(f"{text} -> {pred}")


if __name__ == "__main__":
    main()