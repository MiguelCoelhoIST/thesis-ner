import json
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)


TRAIN_PATH = Path("data/processed/roles_v4.jsonl")
EVAL_PATH = Path("data/eval/roles_eval_realistic_v2.jsonl")
RESULTS_PATH = Path("results/experiment_14_bge_m3_error_analysis.txt")

MODEL_NAME = "BAAI/bge-m3"
LABELS = ["ARGUIDO", "RELATOR", "REU", "TESTEMUNHA", "UNKNOWN"]


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


def extract_target_entity(text):
    start_marker = "[ENTITY]"
    end_marker = "[/ENTITY]"

    start = text.find(start_marker)
    end = text.find(end_marker)

    if start == -1 or end == -1 or end <= start:
        return ""

    start += len(start_marker)
    return text[start:end].strip()


def format_confusion_matrix(matrix):
    label_width = max(len(label) for label in LABELS)
    value_width = max(5, len(str(matrix.max())))

    header = " " * (label_width + 2)
    header += " ".join(label.rjust(value_width) for label in LABELS)

    lines = [header]
    for label, row in zip(LABELS, matrix):
        values = " ".join(str(value).rjust(value_width) for value in row)
        lines.append(f"{label.ljust(label_width)}  {values}")

    return "\n".join(lines)


def build_results_text(
    train_texts,
    eval_texts,
    eval_labels,
    predictions,
    accuracy,
    macro_f1,
    report,
    matrix,
):
    misclassified = [
        {
            "text": text,
            "target_entity": extract_target_entity(text),
            "gold": gold,
            "predicted": predicted,
        }
        for text, gold, predicted in zip(eval_texts, eval_labels, predictions)
        if gold != predicted
    ]

    lines = [
        "Experiment 14 - BGE-M3 error analysis",
        "",
        "Model:",
        MODEL_NAME,
        "",
        "Classifier:",
        "LogisticRegression over frozen sentence embeddings",
        "",
        "Datasets:",
        f"train: {TRAIN_PATH}",
        f"eval: {EVAL_PATH}",
        f"train examples: {len(train_texts)}",
        f"eval examples: {len(eval_texts)}",
        "",
        "Results:",
        f"accuracy: {accuracy:.4f}",
        f"macro_f1: {macro_f1:.4f}",
        "",
        "Classification report:",
        report,
        "",
        "Confusion matrix:",
        "Rows = gold labels, columns = predicted labels",
        format_confusion_matrix(matrix),
        "",
        "Misclassified examples:",
    ]

    if not misclassified:
        lines.append("None")
    else:
        for index, example in enumerate(misclassified, start=1):
            lines.extend(
                [
                    "",
                    f"{index}.",
                    f"Text: {example['text']}",
                    f"Target entity: {example['target_entity']}",
                    f"Gold label: {example['gold']}",
                    f"Predicted label: {example['predicted']}",
                ]
            )

    return "\n".join(lines)


def main():
    print("Loading datasets...")

    train_texts, train_labels = load_jsonl(TRAIN_PATH)
    eval_texts, eval_labels = load_jsonl(EVAL_PATH)

    print(f"Train examples: {len(train_texts)}")
    print(f"Eval examples: {len(eval_texts)}")

    print(f"\nLoading encoder: {MODEL_NAME}")
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
    _, _, macro_f1, _ = precision_recall_fscore_support(
        eval_labels,
        predictions,
        average="macro",
        zero_division=0,
    )
    report = classification_report(eval_labels, predictions, zero_division=0)
    matrix = confusion_matrix(eval_labels, predictions, labels=LABELS)

    results_text = build_results_text(
        train_texts=train_texts,
        eval_texts=eval_texts,
        eval_labels=eval_labels,
        predictions=predictions,
        accuracy=accuracy,
        macro_f1=macro_f1,
        report=report,
        matrix=matrix,
    )

    print("\n" + results_text)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        f.write(results_text)
        f.write("\n")

    print(f"\nSaved results to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
