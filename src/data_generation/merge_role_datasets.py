import json
from pathlib import Path

INPUT_FILES = [
    Path("data/processed/roles_v3.jsonl"),
    Path("data/processed/roles_hard_multi_entity.jsonl"),
]

OUTPUT_FILE = Path("data/processed/roles_v4.jsonl")


def main():
    merged = []

    for path in INPUT_FILES:
        print(f"Loading: {path}")

        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                merged.append(json.loads(line))

    print(f"Total examples: {len(merged)}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for example in merged:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"Saved merged dataset to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()