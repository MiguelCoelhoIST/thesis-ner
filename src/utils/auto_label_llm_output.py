import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a Named Entity Recognition annotator for Portuguese legal text.

Recognized labels:
- PER: person
- ORG: organization/company/institution
- LOC: address/location
- DAT: personal or relevant date
- IDP: identifier such as NIF, IBAN, passport, CC, plate
- LEGROLE: legal role such as arguido, testemunha, réu, vítima, relator

Return only valid JSON in this format:
{
  "entities": [
    {"text": "João Silva", "label": "PER"},
    {"text": "testemunha", "label": "LEGROLE"}
  ]
}

Rules:
- Do not explain.
- Do not include entities not present in the sentence.
- Prefer the full surface form appearing in the text.
- If there are no entities, return {"entities": []}.
"""

def label_sentence(sentence: str):
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": sentence},
        ],
    )
    content = response.choices[0].message.content.strip()
    return json.loads(content)

def find_spans(text, labeled_entities):
    spans = []
    used = []
    for ent in labeled_entities:
        value = ent["text"]
        label = ent["label"]

        start = text.find(value)
        if start == -1:
            continue

        end = start + len(value)

        # Avoid duplicate identical spans if repeated
        if (start, end, label) in used:
            continue

        used.append((start, end, label))
        spans.append([start, end, label])

    return spans

def process_file(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            row = json.loads(line)
            text = row["text"]

            try:
                ann = label_sentence(text)
                spans = find_spans(text, ann["entities"])
                output = {
                    "text": text,
                    "entities": spans
                }
            except Exception:
                output = {
                    "text": text,
                    "entities": []
                }

            fout.write(json.dumps(output, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    process_file(
        "data/processed/llm_generated_sentences.jsonl",
        "data/processed/llm_generated_labeled.jsonl"
    )