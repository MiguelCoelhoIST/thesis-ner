import json
import re
from pathlib import Path
from collections import Counter

from sklearn.metrics import accuracy_score, classification_report

EVAL_PATH = Path("data/eval/roles_eval_realistic_harder.jsonl")

ENTITY_START = "[entity]"
ENTITY_END = "[/entity]"


ROLE_TERMS = {
    "ARGUIDO": ["arguido", "arguida"],
    "TESTEMUNHA": ["testemunha"],
    "RELATOR": ["relator", "relatora", "juiz relator", "juíza relatora"],
    "REU": ["réu", "ré"],
}


def load_dataset(path: Path):
    examples = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            examples.append(json.loads(line))

    return examples


def mark_entity(text: str, entity: str):
    if entity not in text:
        raise ValueError(f"Entity '{entity}' not found in text: {text}")

    return text.replace(entity, f"{ENTITY_START} {entity} {ENTITY_END}", 1)


def normalize(text: str):
    return text.lower()


def build_patterns(role_terms):
    patterns = []

    for term in role_terms:
        # Role before entity:
        # "o arguido [ENTITY] João [/ENTITY]"
        # "a testemunha [ENTITY] Ana [/ENTITY]"
        patterns.append(rf"\b{term}\b\s+{re.escape(ENTITY_START)}")

        # Role after entity:
        # "[ENTITY] João [/ENTITY] como arguido"
        patterns.append(rf"{re.escape(ENTITY_END)}\s+como\s+\b{term}\b")

        # "[ENTITY] João [/ENTITY], arguido nos autos"
        patterns.append(rf"{re.escape(ENTITY_END)}\s*,?\s*\b{term}\b")

        # "[ENTITY] João [/ENTITY] na qualidade de arguido"
        patterns.append(rf"{re.escape(ENTITY_END)}\s+na\s+qualidade\s+de\s+\b{term}\b")

        # "[ENTITY] João [/ENTITY] enquanto réu"
        patterns.append(rf"{re.escape(ENTITY_END)}\s+enquanto\s+\b{term}\b")

    return patterns


ROLE_PATTERNS = {
    label: build_patterns(terms)
    for label, terms in ROLE_TERMS.items()
}

ROLE_PATTERNS["RELATOR"].extend([
    rf"\brelatado\s+por\s+{re.escape(ENTITY_START)}",
    rf"\bacórdão\s+relatado\s+por\s+{re.escape(ENTITY_START)}",
])


def predict_role(marked_text: str):
    text = marked_text.lower()

    matches = []

    for label, patterns in ROLE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                matches.append((match.start(), label, pattern))

    if not matches:
        return "UNKNOWN"

    matches.sort(key=lambda x: x[0])
    return matches[0][1]


def main():
    examples = load_dataset(EVAL_PATH)

    gold_labels = []
    predictions = []

    print(f"Loaded eval examples: {len(examples)}")

    for example in examples:
        text = example["text"]
        entity = example["entity"]
        gold = example["label"]

        marked = mark_entity(text, entity)
        pred = predict_role(marked)

        gold_labels.append(gold)
        predictions.append(pred)

        print("\nTEXT:", text)
        print("ENTITY:", entity)
        print("MARKED:", marked)
        print("GOLD:", gold)
        print("PRED:", pred)

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