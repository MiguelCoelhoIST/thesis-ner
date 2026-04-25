import argparse
import json
from pathlib import Path

import spacy
from spacy.tokens import DocBin

# Converts your generated/labeled JSONL into spaCy DocBin format.
# EX:
# python .\src\data\convert_jsonl_to_spacy.py --input .\data\processed\synthetic_legal_ner.jsonl --output .\data\processed\synthetic_legal_ner.spacy

def convert_jsonl_to_spacy(input_path: str, output_path: str, lang: str = "pt") -> None:
    nlp = spacy.blank(lang)
    doc_bin = DocBin(store_user_data=True)

    total_docs = 0
    kept_docs = 0
    skipped_entities = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {line_no}: invalid JSON, skipping. Error: {e}")
                continue

            text = row.get("text", "")
            entities = row.get("entities", [])

            if not text:
                print(f"[WARN] Line {line_no}: empty text, skipping.")
                continue

            total_docs += 1
            doc = nlp.make_doc(text)

            spans = []
            for ent in entities:
                try:
                    start, end, label = ent
                except Exception:
                    print(f"[WARN] Line {line_no}: bad entity format {ent}, skipping entity.")
                    skipped_entities += 1
                    continue

                span = doc.char_span(start, end, label=label, alignment_mode="contract")
                if span is None:
                    print(
                        f"[WARN] Line {line_no}: could not create span "
                        f"({start}, {end}, {label}) -> {text[start:end]!r}"
                    )
                    skipped_entities += 1
                    continue

                spans.append(span)

            # Filter overlapping spans: keep longest first
            spans = sorted(spans, key=lambda s: (s.start_char, -(s.end_char - s.start_char)))
            filtered = []
            occupied = set()

            for span in spans:
                token_range = set(range(span.start, span.end))
                if occupied & token_range:
                    skipped_entities += 1
                    continue
                filtered.append(span)
                occupied |= token_range

            doc.ents = filtered
            doc_bin.add(doc)
            kept_docs += 1

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc_bin.to_disk(output_path)

    print(f"[DONE] Saved DocBin to: {output_path}")
    print(f"Total docs read: {total_docs}")
    print(f"Docs written: {kept_docs}")
    print(f"Skipped entities: {skipped_entities}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert labeled JSONL to spaCy .spacy DocBin")
    parser.add_argument("--input", required=True, help="Path to labeled JSONL")
    parser.add_argument("--output", required=True, help="Output .spacy path")
    parser.add_argument("--lang", default="pt", help="spaCy language code (default: pt)")
    args = parser.parse_args()

    convert_jsonl_to_spacy(args.input, args.output, args.lang)