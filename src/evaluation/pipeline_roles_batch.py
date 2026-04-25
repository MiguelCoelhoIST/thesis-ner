import spacy
from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
import json

CONFIDENCE_THRESHOLD = 0.40

NER_MODEL_PATH = "models/eduardo_extended_model"
TRAIN_PATH = Path("data/processed/roles_v3.jsonl")
INPUT_PATH = Path("data/eval/realistic_role_eval.txt")


def load_training_data():
    texts = []
    labels = []

    with TRAIN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            texts.append(record["text"])
            labels.append(record["label"])

    return texts, labels


def train_classifier():
    texts, labels = load_training_data()

    vectorizer = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    X = vectorizer.fit_transform(texts)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)

    return vectorizer, clf


def predict_role(text, vectorizer, clf):
    X = vectorizer.transform([text])
    probs = clf.predict_proba(X)[0]
    pred = clf.predict(X)[0]

    max_prob = max(probs)

    if max_prob < CONFIDENCE_THRESHOLD:
        return None  # melhor que UNKNOWN aqui
    return pred

def get_local_context(text, start_char, end_char, window=50):
    start = max(0, start_char - window)
    end = min(len(text), end_char + window)
    return text[start:end]

def mark_entity(context, entity_text):
    return context.replace(entity_text, f"[ENTITY] {entity_text} [/ENTITY]", 1)


def main():
    print("Loading NER model...")
    nlp = spacy.load(NER_MODEL_PATH)

    print("Training role classifier...")
    vectorizer, clf = train_classifier()

    print("\nProcessing texts...\n")

    with INPUT_PATH.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            text = line.strip()
            if not text:
                continue

            print("=" * 60)
            print(f"TEXT {i+1}: {text}\n")

            doc = nlp(text)

            for ent in doc.ents:
                if ent.label_ == "PER":
                    context = get_local_context(text, ent.start_char, ent.end_char)
                    marked_context = mark_entity(context, ent.text)

                    role = predict_role(marked_context, vectorizer, clf)

                    if role:
                        print(f"{ent.text} -> PER -> {role}")
                        print(f"  context: {marked_context}")
                    else:
                        print(f"{ent.text} -> PER")
                        print(f"  context: {marked_context}")

                else:
                    print(f"{ent.text} -> {ent.label_}")


if __name__ == "__main__":
    main()