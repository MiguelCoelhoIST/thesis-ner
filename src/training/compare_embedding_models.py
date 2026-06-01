import json
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
)

TRAIN_PATH = Path("data/processed/roles_v4.jsonl")
EVAL_PATH = Path("data/eval/roles_eval_realistic.jsonl")
RESULTS_PATH = Path("results/experiment_13_encoder_comparison.txt")

MODELS = [
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "intfloat/multilingual-e5-base",
    "BAAI/bge-m3",
]


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


def evaluate_model(model_name, train_texts, train_labels, eval_texts, eval_labels):
    print(f"\n=== Evaluating encoder: {model_name} ===")

    start = time.time()

    encoder = SentenceTransformer(model_name)

    X_train = encoder.encode(train_texts, show_progress_bar=True)
    X_eval = encoder.encode(eval_texts, show_progress_bar=True)

    classifier = LogisticRegression(max_iter=2000)
    classifier.fit(X_train, train_labels)

    predictions = classifier.predict(X_eval)

    accuracy = accuracy_score(eval_labels, predictions)

    precision, recall, f1, _ = precision_recall_fscore_support(
        eval_labels,
        predictions,
        average="macro",
        zero_division=0,
    )

    runtime = time.time() - start

    report = classification_report(eval_labels, predictions, zero_division=0)

    return {
        "model": model_name,
        "accuracy": accuracy,
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1,
        "runtime_seconds": runtime,
        "classification_report": report,
    }


def main():
    print("Loading datasets...")

    train_texts, train_labels = load_jsonl(TRAIN_PATH)
    eval_texts, eval_labels = load_jsonl(EVAL_PATH)

    print(f"Train examples: {len(train_texts)}")
    print(f"Eval examples: {len(eval_texts)}")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_results = []

    for model_name in MODELS:
        result = evaluate_model(
            model_name,
            train_texts,
            train_labels,
            eval_texts,
            eval_labels,
        )
        all_results.append(result)

    all_results = sorted(all_results, key=lambda r: r["macro_f1"], reverse=True)

    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        f.write("Experiment 13 - Encoder comparison\n\n")
        f.write(f"Train dataset: {TRAIN_PATH}\n")
        f.write(f"Eval dataset: {EVAL_PATH}\n")
        f.write(f"Train examples: {len(train_texts)}\n")
        f.write(f"Eval examples: {len(eval_texts)}\n\n")

        for result in all_results:
            f.write("=" * 80 + "\n")
            f.write(f"Model: {result['model']}\n")
            f.write(f"Accuracy: {result['accuracy']:.4f}\n")
            f.write(f"Macro Precision: {result['macro_precision']:.4f}\n")
            f.write(f"Macro Recall: {result['macro_recall']:.4f}\n")
            f.write(f"Macro F1: {result['macro_f1']:.4f}\n")
            f.write(f"Runtime seconds: {result['runtime_seconds']:.2f}\n\n")
            f.write("Classification report:\n")
            f.write(result["classification_report"])
            f.write("\n\n")

    print(f"\nSaved results to: {RESULTS_PATH}")

    print("\nSummary:")
    for result in all_results:
        print(
            f"{result['model']} | "
            f"macro_f1={result['macro_f1']:.4f} | "
            f"accuracy={result['accuracy']:.4f} | "
            f"runtime={result['runtime_seconds']:.2f}s"
        )


if __name__ == "__main__":
    main()