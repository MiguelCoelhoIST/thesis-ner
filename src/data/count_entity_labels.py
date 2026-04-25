### Shows:
# total docs
# total entities
# counts by label
###
import spacy
from spacy.tokens import DocBin
from collections import Counter

nlp = spacy.blank("pt")

doc_bin = DocBin().from_disk("data/raw/silver.spacy")
docs = list(doc_bin.get_docs(nlp.vocab))

print(f"Total docs: {len(docs)}")

label_counter = Counter()
entity_counter = 0

for doc in docs:
    for ent in doc.ents:
        label_counter[ent.label_] += 1
        entity_counter += 1

print(f"Total entities: {entity_counter}")
print("\nEntity counts by label:")
for label, count in label_counter.most_common():
    print(f"{label}: {count}")