import spacy

baseline = spacy.load("models/baseline_model")
extended = spacy.load("models/eduardo_extended_model")

with open("data/eval/manual_eval.txt", "r", encoding="utf-8") as f:
    texts = [line.strip() for line in f if line.strip()]

with open("results/model_comparison_02.txt", "w", encoding="utf-8") as out:

    for i, text in enumerate(texts, start=1):
        out.write(f"\n===== EXAMPLE {i} =====\n")
        out.write(f"TEXT: {text}\n\n")

        doc1 = baseline(text)
        doc2 = extended(text)

        out.write("BASELINE:\n")
        if doc1.ents:
            for ent in doc1.ents:
                out.write(f"{ent.text} -> {ent.label_}\n")
        else:
            out.write("No entities found\n")

        out.write("\nEXTENDED:\n")
        if doc2.ents:
            for ent in doc2.ents:
                out.write(f"{ent.text} -> {ent.label_}\n")
        else:
            out.write("No entities found\n")

        out.write("\n")