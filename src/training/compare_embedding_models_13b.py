import json
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_recall_fscore_support,
)


TRAIN_PATH = Path("data/processed/roles_v4.jsonl")
EVAL_PATH = Path("data/eval/roles_eval_realistic_v2.jsonl")
RESULTS_PATH = Path(
    "results/experiment_13b_encoder_comparison_corrected_markers.txt"
)

MODELS = [
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "intfloat/multilingual-e5-base",
    "BAAI/bge-m3",
]

START_MARKER = "[ENTITY]"
END_MARKER = "[/ENTITY]"


def normalize_entity_marker_spacing(text):
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise ValueError("text must contain exactly one pair of entity markers")

    marker_start = text.index(START_MARKER)
    entity_start = marker_start + len(START_MARKER)
    marker_end = text.index(END_MARKER, entity_start)
    entity = text[entity_start:marker_end].strip()
    if not entity:
        raise ValueError("entity marker span must not be empty")

    return (
        text[:marker_start]
        + f"{START_MARKER} {entity} {END_MARKER}"
        + text[marker_end + len(END_MARKER) :]
    )


def load_training_data(path):
    texts = []
    labels = []

    with path.open("r", encoding="utf-8") as dataset:
        for line in dataset:
            if not line.strip():
                continue
            record = json.loads(line)
            texts.append(record["text"])
            labels.append(record["label"])

    return texts, labels


def load_normalized_evaluation_data(path):
    texts = []
    labels = []
    changed_count = 0

    with path.open("r", encoding="utf-8") as dataset:
        for line_number, line in enumerate(dataset, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            try:
                normalized = normalize_entity_marker_spacing(record["text"])
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc

            if normalized != record["text"]:
                changed_count += 1
            texts.append(normalized)
            labels.append(record["label"])

    if not all(
        text.count("[ENTITY] ") == 1 and text.count(" [/ENTITY]") == 1
        for text in texts
    ):
        raise ValueError("not all evaluation texts use canonical marker spacing")

    return texts, labels, changed_count


def evaluate_model(model_name, train_texts, train_labels, eval_texts, eval_labels):
    print(f"\n=== Evaluating encoder: {model_name} ===")
    start = time.time()

    encoder = SentenceTransformer(model_name)
    train_embeddings = encoder.encode(train_texts, show_progress_bar=True)
    eval_embeddings = encoder.encode(eval_texts, show_progress_bar=True)

    classifier = LogisticRegression(max_iter=2000)
    classifier.fit(train_embeddings, train_labels)
    predictions = classifier.predict(eval_embeddings)

    accuracy = accuracy_score(eval_labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        eval_labels,
        predictions,
        average="macro",
        zero_division=0,
    )
    report = classification_report(eval_labels, predictions, zero_division=0)

    return {
        "model": model_name,
        "accuracy": accuracy,
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1,
        "runtime_seconds": time.time() - start,
        "classification_report": report,
    }


def main():
    print("Loading datasets...")
    train_texts, train_labels = load_training_data(TRAIN_PATH)
    eval_texts, eval_labels, changed_count = load_normalized_evaluation_data(
        EVAL_PATH
    )

    print(f"Train examples: {len(train_texts)}")
    print(f"Eval examples: {len(eval_texts)}")
    print(f"Evaluation texts normalized in memory: {changed_count}")

    results = [
        evaluate_model(
            model_name,
            train_texts,
            train_labels,
            eval_texts,
            eval_labels,
        )
        for model_name in MODELS
    ]
    results.sort(key=lambda result: result["macro_f1"], reverse=True)

    lines = [
        "Experiment 13b - Corrected entity-marker spacing rerun",
        "",
        "CORRECTED RERUN OF EXPERIMENT 13",
        "",
        "The original 240-example evaluation dataset was not modified.",
        "Entity-marker spacing was normalized in memory to:",
        "[ENTITY] entity [/ENTITY]",
        "",
        f"Train dataset: {TRAIN_PATH}",
        f"Evaluation dataset: {EVAL_PATH}",
        f"Train examples: {len(train_texts)}",
        f"Evaluation examples: {len(eval_texts)}",
        f"Evaluation texts changed in memory: {changed_count}",
        f"Evaluation texts already canonical: {len(eval_texts) - changed_count}",
        "Classifier: LogisticRegression(max_iter=2000)",
        "",
    ]

    for result in results:
        lines.extend(
            [
                "=" * 80,
                f"Model: {result['model']}",
                f"Accuracy: {result['accuracy']:.4f}",
                f"Macro Precision: {result['macro_precision']:.4f}",
                f"Macro Recall: {result['macro_recall']:.4f}",
                f"Macro F1: {result['macro_f1']:.4f}",
                f"Runtime seconds: {result['runtime_seconds']:.2f}",
                "",
                "Per-class metrics:",
                result["classification_report"],
                "",
            ]
        )

    results_text = "\n".join(lines)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(results_text + "\n", encoding="utf-8")

    print("\n" + results_text)
    print(f"Saved results to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
