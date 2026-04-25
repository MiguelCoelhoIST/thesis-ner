import argparse
from pathlib import Path

import spacy
from spacy.tokens import DocBin

# Merges multiple .spacy datasets into one.
# EX:
# python .\src\data\merge_datasets.py --inputs .\data\raw\silver.spacy .\data\processed\synthetic_legal_ner.spacy --output .\data\processed\silver_plus_synth.spacy

def load_docs(spacy_path: str, lang: str = "pt"):
    nlp = spacy.blank(lang)
    doc_bin = DocBin().from_disk(spacy_path)
    return list(doc_bin.get_docs(nlp.vocab))


def merge_spacy_files(inputs, output, lang="pt"):
    merged = DocBin(store_user_data=True)
    total = 0

    for path in inputs:
        docs = load_docs(path, lang=lang)
        print(f"[INFO] Loaded {len(docs)} docs from {path}")
        for doc in docs:
            merged.add(doc)
        total += len(docs)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    merged.to_disk(output)

    print(f"[DONE] Merged {total} docs into: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple .spacy datasets")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input .spacy files")
    parser.add_argument("--output", required=True, help="Merged output .spacy file")
    parser.add_argument("--lang", default="pt", help="spaCy language code (default: pt)")
    args = parser.parse_args()

    merge_spacy_files(args.inputs, args.output, args.lang)