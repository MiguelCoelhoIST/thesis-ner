import json
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

TRAIN_PATH = Path("data/processed/roles_v4.jsonl")
EVAL_PATH = Path("data/eval/roles_eval_realistic.jsonl")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


def load_jsonl(path):
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
    print("Loading datasets...")

    train_texts, train_labels = load_jsonl(TRAIN_PATH)
    eval_texts, eval_labels = load_jsonl(EVAL_PATH)

    print(f"Train examples: {len(train_texts)}")
    print(f"Eval examples: {len(eval_texts)}")

    print("\nLoading embedding model...")
    encoder = SentenceTransformer(MODEL_NAME)

    print("\nGenerating embeddings...")
    X_train = encoder.encode(train_texts, show_progress_bar=True)
    X_eval = encoder.encode(eval_texts, show_progress_bar=True)

    print("\nTraining classifier...")
    classifier = LogisticRegression(max_iter=2000)

    classifier.fit(X_train, train_labels)

    print("\nEvaluating...")
    predictions = classifier.predict(X_eval)

    accuracy = accuracy_score(eval_labels, predictions)

    precision, recall, f1, _ = precision_recall_fscore_support(
        eval_labels,
        predictions,
        average="macro",
        zero_division=0,
    )

    print("\nResults:")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro Precision: {precision:.4f}")
    print(f"Macro Recall: {recall:.4f}")
    print(f"Macro F1: {f1:.4f}")

    print("\nClassification Report:")
    print(classification_report(eval_labels, predictions))


if __name__ == "__main__":
    main()