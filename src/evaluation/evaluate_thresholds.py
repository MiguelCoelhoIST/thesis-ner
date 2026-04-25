import json
from pathlib import Path
from collections import Counter

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score


TRAIN_PATH = Path("data/processed/roles_v2.jsonl")

EVAL_FILES = {
    "normal": Path("data/eval/roles_eval.jsonl"),
    "hard": Path("data/eval/roles_eval_hard.jsonl"),
}

THRESHOLDS = [0.00, 0.40, 0.45, 0.50, 0.60]


def load_dataset(path: Path):
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


def apply_threshold(classifier, probabilities, raw_predictions, threshold):
    predictions = []

    for probs, raw_pred in zip(probabilities, raw_predictions):
        max_prob = max(probs)

        if max_prob < threshold:
            predictions.append("UNKNOWN")
        else:
            predictions.append(raw_pred)

    return predictions


def main():
    print("Loading training data...")
    train_texts, train_labels = load_dataset(TRAIN_PATH)

    vectorizer = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    X_train = vectorizer.fit_transform(train_texts)

    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(X_train, train_labels)

    for eval_name, eval_path in EVAL_FILES.items():
        print(f"\n==============================")
        print(f"EVALUATION SET: {eval_name}")
        print(f"File: {eval_path}")

        eval_texts, eval_labels = load_dataset(eval_path)
        X_eval = vectorizer.transform(eval_texts)

        probabilities = classifier.predict_proba(X_eval)
        raw_predictions = classifier.predict(X_eval)

        for threshold in THRESHOLDS:
            predictions = apply_threshold(
                classifier,
                probabilities,
                raw_predictions,
                threshold
            )

            accuracy = accuracy_score(eval_labels, predictions)
            macro_f1 = f1_score(eval_labels, predictions, average="macro")

            print(f"\nThreshold: {threshold:.2f}")
            print(f"Accuracy: {accuracy:.4f}")
            print(f"Macro F1: {macro_f1:.4f}")
            print(f"Prediction counts: {Counter(predictions)}")


if __name__ == "__main__":
    main()