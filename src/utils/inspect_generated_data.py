import argparse
import json
from pathlib import Path

import spacy
from spacy.tokens import DocBin

# Lets you preview JSONL or .spacy data and see labels quickly.
# EX:
# python .\src\data\inspect_generated_data.py --input .\data\processed\synthetic_legal_ner.jsonl --limit 15
# python .\src\data\inspect_generated_data.py --input .\data\processed\synthetic_legal_ner.spacy --limit 15

def inspect_jsonl(path: str, limit: int = 10):
    print(f"[INFO] Inspecting JSONL: {path}")
    labels = set()

    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if i > limit:
                break

            row = json.loads(line)
            print("\nTEXT:", row["text"])
            for start, end, label in row.get("entities", []):
                print(f"  - {row['text'][start:end]!r} -> {label}")
                labels.add(label)

    print("\nLabels found:", sorted(labels))


def inspect_spacy(path: str, limit: int = 10, lang: str = "pt"):
    print(f"[INFO] Inspecting spaCy DocBin: {path}")
    nlp = spacy.blank(lang)
    doc_bin = DocBin().from_disk(path)
    docs = list(doc_bin.get_docs(nlp.vocab))

    print(f"Total docs: {len(docs)}")

    labels = set()
    for doc in docs[:limit]:
        print("\nTEXT:", doc.text)
        for ent in doc.ents:
            print(f"  - {ent.text!r} -> {ent.label_}")
            labels.add(ent.label_)

    print("\nLabels found:", sorted(labels))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect generated NER data")
    parser.add_argument("--input", required=True, help="Input file (.jsonl or .spacy)")
    parser.add_argument("--limit", type=int, default=10, help="Number of examples to preview")
    parser.add_argument("--lang", default="pt", help="spaCy language code (default: pt)")
    args = parser.parse_args()

    suffix = Path(args.input).suffix.lower()
    if suffix == ".jsonl":
        inspect_jsonl(args.input, args.limit)
    elif suffix == ".spacy":
        inspect_spacy(args.input, args.limit, args.lang)
    else:
        raise ValueError("Unsupported file type. Use .jsonl or .spacy")