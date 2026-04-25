### Shows:
# total docs
# sample texts
# sample entities
# labels found
###
import spacy
from spacy.tokens import DocBin

nlp = spacy.blank("pt")

doc_bin = DocBin().from_disk("data/raw/silver.spacy")
docs = list(doc_bin.get_docs(nlp.vocab)) 

print(f"Total docs: {len(docs)}")

labels = set()

for doc in docs[:10]:  # só primeiros exemplos
    print("\nTEXT:", doc.text)
    for ent in doc.ents:
        print(ent.text, ent.label_)
        labels.add(ent.label_)

print("\nLabels found:", labels)