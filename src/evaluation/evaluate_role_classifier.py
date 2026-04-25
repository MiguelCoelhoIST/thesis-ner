import json
from pathlib import Path
from collections import Counter

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score


TRAIN_PATH = Path("data/processed/roles_v2.jsonl")
EVAL_PATH = Path("data/eval/roles_eval_hard.jsonl")

CONFIDENCE_THRESHOLD = 0.40


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


def main():
    print("Loading training data...")
    train_texts, train_labels = load_dataset(TRAIN_PATH)

    print("Loading evaluation data...")
    eval_texts, eval_labels = load_dataset(EVAL_PATH)

    print(f"Train examples: {len(train_texts)}")
    print(f"Eval examples: {len(eval_texts)}")
    print(f"Train labels: {sorted(set(train_labels))}")
    print(f"Eval labels: {sorted(set(eval_labels))}")

    print("\nTraining classifier...")
    vectorizer = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    X_train = vectorizer.fit_transform(train_texts)

    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(X_train, train_labels)

    print("Evaluating...")
    X_eval = vectorizer.transform(eval_texts)

    probabilities = classifier.predict_proba(X_eval)
    raw_predictions = classifier.predict(X_eval)

    predictions = []

    for probs, raw_pred in zip(probabilities, raw_predictions):
        max_prob = max(probs)

        if max_prob < CONFIDENCE_THRESHOLD:
            predictions.append("UNKNOWN")
        else:
            predictions.append(raw_pred)

    accuracy = accuracy_score(eval_labels, predictions)

    print(f"\nAccuracy: {accuracy:.4f}")

    print("\nClassification report:")
    print(classification_report(eval_labels, predictions, zero_division=0))

    print("\nErrors:")
    errors = 0
    

    for idx, (text, gold, pred) in enumerate(zip(eval_texts, eval_labels, predictions)):
        if gold != pred:
            errors += 1
            print(f"- TEXT: {text}")
            print(f"  GOLD: {gold}")
            print(f"  PRED: {pred}")

            ranked = sorted(
                zip(classifier.classes_, probabilities[idx]),
                key=lambda x: x[1],
                reverse=True
            )

            print("  PROBABILITIES:")
            for label, prob in ranked:
                print(f"    {label}: {prob:.4f}")

    if errors == 0:
        print("No errors found.")

    print("\nPrediction counts:")
    print(Counter(predictions))


if __name__ == "__main__":
    main()