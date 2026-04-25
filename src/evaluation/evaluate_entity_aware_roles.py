import json
from pathlib import Path
from collections import Counter

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report


TRAIN_PATH = Path("data/processed/roles_v3.jsonl")
EVAL_PATH = Path("data/eval/roles_eval_realistic.jsonl")
CONFIDENCE_THRESHOLD = 0.40


def load_dataset(path: Path):
    texts = []
    labels = []
    entities = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            texts.append(record["text"])
            labels.append(record["label"])
            entities.append(record["entity"])

    return texts, entities, labels


def mark_entity(text: str, entity: str):
    if entity not in text:
        raise ValueError(f"Entity '{entity}' not found in text: {text}")

    return text.replace(entity, f"[ENTITY] {entity} [/ENTITY]", 1)


def apply_threshold(classifier, probabilities, raw_predictions):
    predictions = []

    for probs, raw_pred in zip(probabilities, raw_predictions):
        max_prob = max(probs)

        if max_prob < CONFIDENCE_THRESHOLD:
            predictions.append("UNKNOWN")
        else:
            predictions.append(raw_pred)

    return predictions


def main():
    print("Loading training data...")
    train_texts, train_entities, train_labels = load_dataset(TRAIN_PATH)

    print("Loading evaluation data...")
    eval_texts, eval_entities, eval_labels = load_dataset(EVAL_PATH)

    marked_train_texts = [
        text if "[ENTITY]" in text else mark_entity(text, entity)
        for text, entity in zip(train_texts, train_entities)
    ]

    marked_eval_texts = [
        mark_entity(text, entity)
        for text, entity in zip(eval_texts, eval_entities)
    ]

    print(f"Train examples: {len(marked_train_texts)}")
    print(f"Eval examples: {len(marked_eval_texts)}")
    print(f"Labels: {sorted(set(train_labels))}")

    vectorizer = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    X_train = vectorizer.fit_transform(marked_train_texts)

    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(X_train, train_labels)

    X_eval = vectorizer.transform(marked_eval_texts)

    probabilities = classifier.predict_proba(X_eval)
    raw_predictions = classifier.predict(X_eval)
    predictions = apply_threshold(classifier, probabilities, raw_predictions)

    accuracy = accuracy_score(eval_labels, predictions)

    print(f"\nAccuracy: {accuracy:.4f}")
    print("\nClassification report:")
    print(classification_report(eval_labels, predictions, zero_division=0))

    print("\nErrors:")
    errors = 0

    for idx, (text, entity, gold, pred, marked_text) in enumerate(
        zip(eval_texts, eval_entities, eval_labels, predictions, marked_eval_texts)
    ):
        if gold != pred:
            errors += 1
            print(f"- TEXT: {text}")
            print(f"  ENTITY: {entity}")
            print(f"  MARKED: {marked_text}")
            print(f"  GOLD: {gold}")
            print(f"  PRED: {pred}")

            ranked = sorted(
                zip(classifier.classes_, probabilities[idx]),
                key=lambda x: x[1],
                reverse=True,
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