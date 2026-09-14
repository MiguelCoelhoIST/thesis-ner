import json
import sys
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_recall_fscore_support,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.entity_marking import mark_entity
from src.validate_real_role_dataset import validate_file


TRAIN_PATH = PROJECT_ROOT / "data/processed/roles_v4.jsonl"
EVAL_PATH = PROJECT_ROOT / "data/eval/roles_eval_real_candidates_v1.jsonl"
RESULTS_PATH = PROJECT_ROOT / "results/experiment_15_bge_m3_real_smoke_test.txt"

MODEL_NAME = "BAAI/bge-m3"
EXPECTED_EVAL_EXAMPLES = 10


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


def load_evaluation_data(path):
    records = []

    with path.open("r", encoding="utf-8") as dataset:
        for line in dataset:
            if not line.strip():
                continue

            record = json.loads(line)
            record["marked_text"] = mark_entity(
                record["text"],
                record["entity_start"],
                record["entity_end"],
            )
            records.append(record)

    return records


def build_results_text(
    train_count,
    records,
    predictions,
    accuracy,
    macro_precision,
    macro_recall,
    macro_f1,
    report,
    runtime_seconds,
):
    lines = [
        "Experiment 15 - BGE-M3 real STJ candidate smoke test",
        "",
        "PRELIMINARY SMOKE TEST ON ONLY 10 REAL EXAMPLES - NOT A FINAL EVALUATION",
        "",
        "Model:",
        MODEL_NAME,
        "",
        "Classifier:",
        "LogisticRegression(max_iter=2000) over frozen BGE-M3 embeddings",
        "",
        "Datasets:",
        "train: data/processed/roles_v4.jsonl",
        "eval: data/eval/roles_eval_real_candidates_v1.jsonl",
        f"train examples: {train_count}",
        f"eval examples: {len(records)}",
        "",
        "Predictions:",
    ]

    for index, (record, prediction) in enumerate(
        zip(records, predictions), start=1
    ):
        lines.extend(
            [
                "",
                f"{index}. id: {record['id']}",
                f"entity: {record['entity']}",
                f"gold: {record['label']}",
                f"predicted: {prediction}",
                f"marked text: {record['marked_text']}",
            ]
        )

    lines.extend(
        [
            "",
            "Metrics:",
            f"accuracy: {accuracy:.4f}",
            f"macro_precision: {macro_precision:.4f}",
            f"macro_recall: {macro_recall:.4f}",
            f"macro_f1: {macro_f1:.4f}",
            f"runtime_seconds: {runtime_seconds:.2f}",
            "",
            "Classification report:",
            report,
            "",
            "Interpretation:",
            "These results are a preliminary pipeline smoke test on only 10 real STJ examples. They are not a final or statistically reliable model evaluation.",
        ]
    )

    return "\n".join(lines)


def main():
    print("Validating real evaluation dataset...")
    eval_count, validation_errors = validate_file(EVAL_PATH)
    if validation_errors:
        for error in validation_errors:
            print(error)
        raise ValueError(
            f"Evaluation dataset failed validation with "
            f"{len(validation_errors)} error(s)."
        )
    if eval_count != EXPECTED_EVAL_EXAMPLES:
        raise ValueError(
            f"Expected {EXPECTED_EVAL_EXAMPLES} evaluation examples for this "
            f"smoke test, found {eval_count}."
        )

    print("Loading datasets...")
    train_texts, train_labels = load_training_data(TRAIN_PATH)
    eval_records = load_evaluation_data(EVAL_PATH)
    eval_texts = [record["marked_text"] for record in eval_records]
    eval_labels = [record["label"] for record in eval_records]

    print(f"Train examples: {len(train_texts)}")
    print(f"Eval examples: {len(eval_records)}")
    print("PRELIMINARY SMOKE TEST ON ONLY 10 REAL EXAMPLES - NOT A FINAL EVALUATION")

    start = time.time()

    print(f"\nLoading encoder: {MODEL_NAME}")
    encoder = SentenceTransformer(MODEL_NAME)

    print("\nGenerating embeddings...")
    train_embeddings = encoder.encode(train_texts, show_progress_bar=True)
    eval_embeddings = encoder.encode(eval_texts, show_progress_bar=True)

    print("\nTraining classifier...")
    classifier = LogisticRegression(max_iter=2000)
    classifier.fit(train_embeddings, train_labels)

    predictions = classifier.predict(eval_embeddings)
    runtime_seconds = time.time() - start

    accuracy = accuracy_score(eval_labels, predictions)
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            eval_labels,
            predictions,
            average="macro",
            zero_division=0,
        )
    )
    report = classification_report(eval_labels, predictions, zero_division=0)

    results_text = build_results_text(
        train_count=len(train_texts),
        records=eval_records,
        predictions=predictions,
        accuracy=accuracy,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        report=report,
        runtime_seconds=runtime_seconds,
    )

    print("\n" + results_text)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", encoding="utf-8") as results_file:
        results_file.write(results_text)
        results_file.write("\n")

    print(f"\nSaved results to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
