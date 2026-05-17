import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_PATH = "models/role_transformer_model"

test_sentences = [
    "O testemunho de [ENTITY] Luís Matos [/ENTITY] foi considerado credível.",
    "O arguido [ENTITY] João Ribeiro [/ENTITY] negou os factos.",
    "A testemunha [ENTITY] Carla Sousa [/ENTITY] confirmou a versão apresentada.",
    "O relator [ENTITY] António Silva [/ENTITY] proferiu decisão.",
    "[ENTITY] Maria Ferreira [/ENTITY] reside em Lisboa.",
    "O arguido João Martins foi ouvido e a testemunha [ENTITY] Ana Silva [/ENTITY] prestou declarações.",
    "A testemunha Ana Silva prestou declarações contra o arguido [ENTITY] João Martins [/ENTITY].",
    "No acórdão relatado por [ENTITY] Carlos Mendes [/ENTITY], o recurso foi julgado improcedente.",
    "O réu Pedro Costa foi representado pela mandatária [ENTITY] Sofia Almeida [/ENTITY].",
]

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

model.eval()

for text in test_sentences:
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)
        pred_id = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][pred_id].item()

    label = model.config.id2label[pred_id]

    print(f"\n{text}")
    print(f"Prediction: {label} ({confidence:.2f})")