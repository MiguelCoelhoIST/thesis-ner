import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are generating synthetic Portuguese legal-style sentences for Named Entity Recognition training.

Requirements:
- Use European Portuguese.
- Generate short, realistic, one-sentence legal examples.
- Include people, legal roles, addresses, IDs, organizations, dates and edge cases.
- Keep variation high.
- Return only the sentences, one per line.
"""

USER_PROMPT = """
Generate 30 short Portuguese legal-style sentences.
Balance these entity types across the set:
PER, ORG, LOC, DAT, IDP, LEGROLE.

Include examples with:
- person names
- addresses
- legal roles
- NIF / IBAN / CC / passport numbers
- dates
- company names
- edge cases like abbreviated names, Dr., Eng., postal codes, license plates
"""

def generate_sentences():
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0.8,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
    )
    text = response.choices[0].message.content.strip()
    lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    return lines

def save_sentences_jsonl(sentences, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for s in sentences:
            f.write(json.dumps({"text": s}, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    sentences = generate_sentences()
    save_sentences_jsonl(sentences, "data/processed/llm_generated_sentences.jsonl")
    print(f"Saved {len(sentences)} sentences.")