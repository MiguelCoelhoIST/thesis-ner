import argparse
import random
from pathlib import Path

import spacy
from spacy.tokens import DocBin

# Splits one .spacy dataset into train/dev.
# EX:
# python .\src\data\split_spacy_dataset.py --input .\data\processed\silver_plus_synth.spacy --train-output .\data\processed\train.spacy --dev-output .\data\processed\dev.spacy

def split_spacy_dataset(input_path: str, train_output: str, dev_output: str, train_ratio: float = 0.8, seed: int = 42, lang: str = "pt"):
    nlp = spacy.blank(lang)
    doc_bin = DocBin().from_disk(input_path)
    docs = list(doc_bin.get_docs(nlp.vocab))

    if not docs:
        raise ValueError("Input dataset is empty.")

    random.seed(seed)
    random.shuffle(docs)

    split_idx = int(len(docs) * train_ratio)
    train_docs = docs[:split_idx]
    dev_docs = docs[split_idx:]

    train_bin = DocBin(store_user_data=True)
    dev_bin = DocBin(store_user_data=True)

    for doc in train_docs:
        train_bin.add(doc)
    for doc in dev_docs:
        dev_bin.add(doc)

    Path(train_output).parent.mkdir(parents=True, exist_ok=True)
    Path(dev_output).parent.mkdir(parents=True, exist_ok=True)

    train_bin.to_disk(train_output)
    dev_bin.to_disk(dev_output)

    print(f"[DONE] Input docs: {len(docs)}")
    print(f"Train docs: {len(train_docs)} -> {train_output}")
    print(f"Dev docs:   {len(dev_docs)} -> {dev_output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split a .spacy dataset into train/dev")
    parser.add_argument("--input", required=True, help="Input .spacy file")
    parser.add_argument("--train-output", required=True, help="Train output .spacy")
    parser.add_argument("--dev-output", required=True, help="Dev output .spacy")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train ratio, default 0.8")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--lang", default="pt", help="spaCy language code (default: pt)")
    args = parser.parse_args()

    split_spacy_dataset(
        args.input,
        args.train_output,
        args.dev_output,
        args.train_ratio,
        args.seed,
        args.lang,
    )