import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.evaluate_rule_based_roles_v2 import predict_role
from src.utils.entity_marking import mark_entity
from src.validate_real_role_dataset import validate_file


TRAIN_PATH = PROJECT_ROOT / "data/processed/roles_v4.jsonl"
EVAL_PATH = PROJECT_ROOT / "data/eval/roles_eval_real_candidates_v1.jsonl"
CHALLENGE_PATH = (
    PROJECT_ROOT / "data/eval/roles_eval_multi_entity_challenge_v1.jsonl"
)
REPORT_PATH = PROJECT_ROOT / "results/experiment_16_real_stj_evaluation_v1.txt"
PREDICTIONS_PATH = PROJECT_ROOT / "results/experiment_16_real_stj_predictions_v1.json"

MODEL_NAME = "BAAI/bge-m3"
LABELS = ["ARGUIDO", "TESTEMUNHA", "RELATOR", "REU", "UNKNOWN"]
EXPECTED_EVAL_EXAMPLES = 50
EXPECTED_PER_CLASS = 10


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def load_evaluation_records(path):
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


def require_valid_dataset(path):
    record_count, errors = validate_file(path)
    if errors:
        details = "\n".join(errors)
        raise ValueError(f"Dataset validation failed:\n{details}")
    return record_count


def require_frozen_eval_conditions(records):
    if len(records) != EXPECTED_EVAL_EXAMPLES:
        raise ValueError(
            f"Expected exactly {EXPECTED_EVAL_EXAMPLES} real STJ examples, "
            f"found {len(records)}."
        )

    if not all(record["human_validated"] for record in records):
        raise ValueError("All real STJ evaluation examples must be human validated.")

    label_counts = Counter(record["label"] for record in records)
    expected_counts = {label: EXPECTED_PER_CLASS for label in LABELS}
    if dict(label_counts) != expected_counts:
        raise ValueError(
            f"Expected {EXPECTED_PER_CLASS} examples per class, "
            f"found {dict(label_counts)}."
        )


def calculate_metrics(gold_labels, predictions, labels=None):
    if labels is None:
        present = set(gold_labels) | set(predictions)
        labels = [label for label in LABELS if label in present]

    precision, recall, f1, support = precision_recall_fscore_support(
        gold_labels,
        predictions,
        labels=labels,
        average=None,
        zero_division=0,
    )
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            gold_labels,
            predictions,
            labels=labels,
            average="macro",
            zero_division=0,
        )
    )

    per_class = {
        label: {
            "precision": float(class_precision),
            "recall": float(class_recall),
            "f1": float(class_f1),
            "support": int(class_support),
        }
        for label, class_precision, class_recall, class_f1, class_support in zip(
            labels, precision, recall, f1, support
        )
    }

    return {
        "count": len(gold_labels),
        "labels_in_macro_average": labels,
        "accuracy": float(accuracy_score(gold_labels, predictions)),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(
            gold_labels, predictions, labels=labels
        ).tolist(),
    }


def calculate_grouped_metrics(records, predictions, field):
    grouped = {}
    values = sorted({record[field] for record in records})

    for value in values:
        indices = [
            index for index, record in enumerate(records) if record[field] == value
        ]
        gold = [records[index]["label"] for index in indices]
        predicted = [predictions[index] for index in indices]
        grouped[str(value).lower()] = calculate_metrics(gold, predicted)

    return grouped


def calculate_distractor_metrics(records, predictions):
    indices = [
        index
        for index, record in enumerate(records)
        if record["contains_distractor_role"]
    ]
    if not indices:
        return None

    gold = [records[index]["label"] for index in indices]
    predicted = [predictions[index] for index in indices]
    return calculate_metrics(gold, predicted)


def evaluate_rule_based(records):
    start = time.perf_counter()
    predictions = [predict_role(record["marked_text"]) for record in records]
    runtime = time.perf_counter() - start
    return predictions, runtime


def train_embedding_classifier(train_texts, train_labels):
    encoder = SentenceTransformer(MODEL_NAME)
    train_embeddings = encoder.encode(train_texts, show_progress_bar=True)
    classifier = LogisticRegression(max_iter=2000)
    classifier.fit(train_embeddings, train_labels)
    return encoder, classifier


def predict_with_embedding_classifier(encoder, classifier, records):
    eval_texts = [record["marked_text"] for record in records]
    embeddings = encoder.encode(eval_texts, show_progress_bar=True)
    return classifier.predict(embeddings).tolist()


def build_approach_results(records, predictions, runtime_seconds):
    gold_labels = [record["label"] for record in records]
    return {
        "runtime_seconds": runtime_seconds,
        "overall": calculate_metrics(gold_labels, predictions, labels=LABELS),
        "by_evidence_type": calculate_grouped_metrics(
            records, predictions, "evidence_type"
        ),
        "by_difficulty": calculate_grouped_metrics(
            records, predictions, "difficulty"
        ),
        "distractor_examples": calculate_distractor_metrics(records, predictions),
    }


def format_metric_summary(metrics):
    return [
        f"count: {metrics['count']}",
        f"accuracy: {metrics['accuracy']:.4f}",
        f"macro precision: {metrics['macro_precision']:.4f}",
        f"macro recall: {metrics['macro_recall']:.4f}",
        f"macro F1: {metrics['macro_f1']:.4f}",
    ]


def format_per_class(metrics):
    lines = [
        "label        precision  recall  F1      support",
        "-----------  ---------  ------  ------  -------",
    ]
    for label, values in metrics["per_class"].items():
        lines.append(
            f"{label:<11}  {values['precision']:<9.4f}  "
            f"{values['recall']:<6.4f}  {values['f1']:<6.4f}  "
            f"{values['support']}"
        )
    return lines


def format_confusion_matrix(metrics):
    labels = metrics["labels_in_macro_average"]
    matrix = metrics["confusion_matrix"]
    width = max(10, max(len(label) for label in labels))
    lines = ["Rows = gold labels; columns = predicted labels"]
    lines.append(" " * (width + 2) + " ".join(f"{label:>{width}}" for label in labels))
    for label, row in zip(labels, matrix):
        lines.append(
            f"{label:<{width}}  "
            + " ".join(f"{value:>{width}}" for value in row)
        )
    return lines


def format_grouped_results(title, groups):
    lines = [title]
    for group_name, metrics in groups.items():
        lines.append(f"  {group_name}:")
        lines.extend(f"    {line}" for line in format_metric_summary(metrics))
    return lines


def format_approach_report(name, records, predictions, results):
    lines = [
        "=" * 88,
        name,
        "=" * 88,
        f"runtime seconds: {results['runtime_seconds']:.4f}",
        "runtime scope: approach setup/training (if applicable) plus prediction on the 50 examples",
        "",
        "Headline metrics:",
        *format_metric_summary(results["overall"]),
        "",
        "Per-class metrics:",
        *format_per_class(results["overall"]),
        "",
        "Confusion matrix:",
        *format_confusion_matrix(results["overall"]),
        "",
        *format_grouped_results(
            "Results by evidence_type:", results["by_evidence_type"]
        ),
        "",
        *format_grouped_results(
            "Results by difficulty:", results["by_difficulty"]
        ),
        "",
        "Performance where contains_distractor_role=true:",
    ]

    if results["distractor_examples"] is None:
        lines.append("No matching examples.")
    else:
        lines.extend(format_metric_summary(results["distractor_examples"]))

    lines.extend(["", "Individual predictions:"])
    for index, (record, prediction) in enumerate(zip(records, predictions), start=1):
        lines.append(
            f"{index:02d}. id={record['id']} | entity={record['entity']} | "
            f"gold={record['label']} | predicted={prediction}"
        )

    return lines


def prediction_rows(records, rule_predictions, embedding_predictions):
    return [
        {
            "id": record["id"],
            "entity": record["entity"],
            "gold": record["label"],
            "evidence_type": record["evidence_type"],
            "difficulty": record["difficulty"],
            "contains_distractor_role": record["contains_distractor_role"],
            "rule_based_prediction": rule_prediction,
            "bge_m3_logistic_regression_prediction": embedding_prediction,
        }
        for record, rule_prediction, embedding_prediction in zip(
            records, rule_predictions, embedding_predictions
        )
    ]


def evaluate_challenge(encoder, classifier):
    if not CHALLENGE_PATH.exists():
        return None

    require_valid_dataset(CHALLENGE_PATH)
    records = load_evaluation_records(CHALLENGE_PATH)

    rule_predictions, rule_runtime = evaluate_rule_based(records)
    embedding_start = time.perf_counter()
    embedding_predictions = predict_with_embedding_classifier(
        encoder, classifier, records
    )
    embedding_runtime = time.perf_counter() - embedding_start

    return {
        "dataset": "data/eval/roles_eval_multi_entity_challenge_v1.jsonl",
        "note": (
            "Qualitative multi-entity diagnostic; excluded from all 50-example "
            "headline metrics."
        ),
        "count": len(records),
        "approaches": {
            "entity_aware_rule_based": build_approach_results(
                records, rule_predictions, rule_runtime
            ),
            "bge_m3_logistic_regression": build_approach_results(
                records, embedding_predictions, embedding_runtime
            ),
        },
        "predictions": prediction_rows(
            records, rule_predictions, embedding_predictions
        ),
    }


def format_challenge_report(challenge):
    lines = [
        "=" * 88,
        "Separate qualitative multi-entity diagnostic",
        "=" * 88,
    ]
    if challenge is None:
        lines.append(
            "Not run: data/eval/roles_eval_multi_entity_challenge_v1.jsonl "
            "does not exist."
        )
        return lines

    lines.extend(
        [
            challenge["note"],
            f"examples: {challenge['count']}",
        ]
    )
    for name, results in challenge["approaches"].items():
        lines.extend(
            [
                "",
                name,
                f"runtime seconds: {results['runtime_seconds']:.4f}",
                *format_metric_summary(results["overall"]),
            ]
        )

    lines.extend(["", "Individual diagnostic predictions:"])
    for index, row in enumerate(challenge["predictions"], start=1):
        lines.append(
            f"{index:02d}. id={row['id']} | entity={row['entity']} | "
            f"gold={row['gold']} | rule={row['rule_based_prediction']} | "
            f"bge_m3={row['bge_m3_logistic_regression_prediction']}"
        )
    return lines


def main():
    print("Validating frozen real STJ evaluation set...")
    dataset_hash_before = file_sha256(EVAL_PATH)
    require_valid_dataset(EVAL_PATH)
    records = load_evaluation_records(EVAL_PATH)
    require_frozen_eval_conditions(records)

    print("Confirmed: 50 human-validated examples, 10 per class.")
    print("Deriving canonical marked text from offsets in memory.")

    print("\nEvaluating current entity-aware rule-based classifier...")
    rule_predictions, rule_runtime = evaluate_rule_based(records)

    print("\nLoading roles_v4 training data...")
    train_texts, train_labels = load_training_data(TRAIN_PATH)
    print(f"Training examples: {len(train_texts)}")

    print(f"\nLoading frozen encoder and training classifier: {MODEL_NAME}")
    embedding_start = time.perf_counter()
    encoder, classifier = train_embedding_classifier(train_texts, train_labels)
    embedding_predictions = predict_with_embedding_classifier(
        encoder, classifier, records
    )
    embedding_runtime = time.perf_counter() - embedding_start

    rule_results = build_approach_results(
        records, rule_predictions, rule_runtime
    )
    embedding_results = build_approach_results(
        records, embedding_predictions, embedding_runtime
    )

    print("\nChecking for separate multi-entity diagnostic...")
    challenge = evaluate_challenge(encoder, classifier)

    if file_sha256(EVAL_PATH) != dataset_hash_before:
        raise RuntimeError("Frozen real STJ evaluation dataset changed during the run.")

    report_lines = [
        "Experiment 16 - Final real-STJ evaluation v1",
        "",
        "FIRST EVALUATION ON THE FROZEN 50-EXAMPLE REAL STJ EVALUATION SET",
        "",
        "The 50 examples are human validated and balanced with 10 examples per class.",
        "The real STJ evaluation set was used only for evaluation and was not modified.",
        "Multi-entity challenge examples, when available, are reported separately and never included in headline metrics.",
        "",
        "Configuration:",
        "rule based: current entity-aware classifier from evaluate_rule_based_roles_v2.py",
        f"embedding encoder: {MODEL_NAME} (frozen)",
        "embedding classifier: LogisticRegression(max_iter=2000)",
        "embedding training data only: data/processed/roles_v4.jsonl",
        f"training examples: {len(train_texts)}",
        "evaluation data: data/eval/roles_eval_real_candidates_v1.jsonl",
        f"evaluation SHA-256: {dataset_hash_before}",
        "macro averages use all five target labels for headline metrics; subgroup macro averages use labels present in that subgroup's gold or predictions.",
        "",
        *format_approach_report(
            "Approach 1 - Entity-aware rule-based classifier",
            records,
            rule_predictions,
            rule_results,
        ),
        "",
        *format_approach_report(
            "Approach 2 - Frozen BGE-M3 embeddings + LogisticRegression",
            records,
            embedding_predictions,
            embedding_results,
        ),
        "",
        *format_challenge_report(challenge),
    ]
    report_text = "\n".join(report_lines) + "\n"

    machine_results = {
        "experiment": 16,
        "title": "Final real-STJ evaluation v1",
        "headline": (
            "First evaluation on the frozen 50-example real STJ evaluation set"
        ),
        "evaluation_dataset": "data/eval/roles_eval_real_candidates_v1.jsonl",
        "evaluation_sha256": dataset_hash_before,
        "evaluation_examples": len(records),
        "label_counts": dict(Counter(record["label"] for record in records)),
        "human_validated": all(record["human_validated"] for record in records),
        "training_dataset": "data/processed/roles_v4.jsonl",
        "training_examples": len(train_texts),
        "embedding_model": MODEL_NAME,
        "classifier": "LogisticRegression(max_iter=2000)",
        "approaches": {
            "entity_aware_rule_based": rule_results,
            "bge_m3_logistic_regression": embedding_results,
        },
        "predictions": prediction_rows(
            records, rule_predictions, embedding_predictions
        ),
        "multi_entity_diagnostic": challenge,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    PREDICTIONS_PATH.write_text(
        json.dumps(machine_results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n" + report_text)
    print(f"Saved report to: {REPORT_PATH}")
    print(f"Saved machine-readable predictions to: {PREDICTIONS_PATH}")


if __name__ == "__main__":
    main()
