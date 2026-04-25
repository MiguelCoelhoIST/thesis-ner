import json
import re
from pathlib import Path
from collections import Counter

from sklearn.metrics import accuracy_score, classification_report


EVAL_PATH = Path("data/eval/roles_eval_realistic.jsonl")
WINDOW_CHARS = 80


ROLE_PATTERNS = {
    "ARGUIDO": [
        r"\barguido\b",
        r"\barguida\b",
    ],
    "TESTEMUNHA": [
        r"\btestemunha\b",
    ],
    "RELATOR": [
        r"\brelator\b",
        r"\brelatora\b",
        r"\bjuiz relator\b",
        r"\bjuíza relatora\b",
        r"\bacórdão relatado por\b",
        r"\brelatado por\b",
    ],
    "REU": [
        r"\bréu\b",
        r"\bré\b",
    ],
}


def load_dataset(path: Path):
    examples = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            examples.append(json.loads(line))

    return examples


def get_local_context(text: str, entity: str, window_chars: int = WINDOW_CHARS):
    start = text.find(entity)

    if start == -1:
        raise ValueError(f"Entity '{entity}' not found in text: {text}")

    end = start + len(entity)

    left = max(0, start - window_chars)
    right = min(len(text), end + window_chars)

    return text[left:right]


def predict_role_rule_based(text: str, entity: str):
    context = get_local_context(text, entity).lower()

    matches = []

    for label, patterns in ROLE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, context, flags=re.IGNORECASE)
            if match:
                # Distance between matched role word and entity mention
                entity_pos = context.find(entity.lower())
                distance = abs(match.start() - entity_pos)
                matches.append((distance, label, pattern))

    if not matches:
        return "UNKNOWN"

    # Choose closest role mention to the entity
    matches.sort(key=lambda x: x[0])
    return matches[0][1]


def main():
    examples = load_dataset(EVAL_PATH)

    gold_labels = []
    predictions = []

    print(f"Loaded eval examples: {len(examples)}")
    print(f"Using local window: {WINDOW_CHARS} chars")

    print("\nPredictions:")

    for example in examples:
        text = example["text"]
        entity = example["entity"]
        gold = example["label"]

        pred = predict_role_rule_based(text, entity)

        gold_labels.append(gold)
        predictions.append(pred)

        print(f"\nTEXT: {text}")
        print(f"ENTITY: {entity}")
        print(f"GOLD: {gold}")
        print(f"PRED: {pred}")

    accuracy = accuracy_score(gold_labels, predictions)

    print("\n==============================")
    print(f"Accuracy: {accuracy:.4f}")

    print("\nClassification report:")
    print(classification_report(gold_labels, predictions, zero_division=0))

    print("\nErrors:")
    errors = 0

    for example, gold, pred in zip(examples, gold_labels, predictions):
        if gold != pred:
            errors += 1
            print(f"- TEXT: {example['text']}")
            print(f"  ENTITY: {example['entity']}")
            print(f"  GOLD: {gold}")
            print(f"  PRED: {pred}")

    if errors == 0:
        print("No errors found.")

    print("\nPrediction counts:")
    print(Counter(predictions))


if __name__ == "__main__":
    main()