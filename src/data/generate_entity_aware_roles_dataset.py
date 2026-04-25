import json
import random
from pathlib import Path

OUTPUT_PATH = Path("data/processed/roles_v3.jsonl")

NAMES = [
    "João Martins",
    "Ana Silva",
    "Pedro Costa",
    "Maria Ferreira",
    "Rui Lopes",
    "Sofia Almeida",
    "Carlos Mendes",
    "Helena Cruz",
    "Paulo Rocha",
    "Inês Costa",
    "Manuel Ferreira",
    "Carla Sousa",
    "Tiago Fernandes",
    "Marta Ribeiro",
    "Luís Matos",
    "Teresa Gomes",
]

TEMPLATES = {
    "ARGUIDO": [
        "O arguido {name} foi ouvido em tribunal.",
        "A arguida {name} apresentou a sua defesa.",
        "O arguido {name} compareceu em audiência.",
        "A arguida {name} foi absolvida.",
        "O arguido {name} foi condenado.",
        "O arguido {name} reside na Rua das Flores, em Lisboa.",
        "A arguida {name} mora na Avenida Central, no Porto.",
        "O arguido {name} indicou residência em Coimbra.",
        "{name} foi ouvido como arguido.",
        "O tribunal ouviu {name} como arguido.",
        "{name}, na qualidade de arguido, prestou declarações.",
        "{name}, arguido nos autos, apresentou recurso.",
    ],
    "TESTEMUNHA": [
        "A testemunha {name} prestou declarações.",
        "A testemunha {name} confirmou os factos.",
        "A testemunha {name} foi ouvida em audiência.",
        "A testemunha {name} declarou conhecer o arguido.",
        "A testemunha {name} respondeu às perguntas do tribunal.",
        "A testemunha {name} reside na Rua do Sol, em Braga.",
        "A testemunha {name} mora na Avenida da Liberdade, em Lisboa.",
        "A testemunha {name} indicou residência no Porto.",
        "{name} foi ouvida como testemunha.",
        "O tribunal ouviu {name} como testemunha.",
        "{name}, na qualidade de testemunha, prestou declarações.",
        "{name}, testemunha nos autos, confirmou os factos.",
    ],
    "RELATOR": [
        "O relator {name} proferiu o acórdão.",
        "A relatora {name} apresentou o projeto de acórdão.",
        "O juiz relator {name} assinou a decisão.",
        "A juíza relatora {name} elaborou o relatório.",
        "O relator {name} deu provimento ao recurso.",
        "O relator {name} assinou o acórdão em Lisboa.",
        "A relatora {name} proferiu decisão no Porto.",
        "{name} foi designado relator do processo.",
        "{name}, na qualidade de relator, elaborou o acórdão.",
        "{name}, relator nos autos, proferiu decisão.",
    ],
    "REU": [
        "O réu {name} apresentou contestação.",
        "A ré {name} foi citada.",
        "O réu {name} foi condenado no pagamento da quantia.",
        "A ré {name} alegou desconhecer os factos.",
        "O réu {name} contestou a ação.",
        "O réu {name} reside na Rua Nova, em Faro.",
        "A ré {name} mora na Rua Central, em Aveiro.",
        "O réu {name} indicou residência em Setúbal.",
        "{name} foi citado como réu.",
        "O tribunal citou {name} como réu.",
        "{name}, na qualidade de réu, apresentou contestação.",
        "{name}, réu nos autos, contestou a ação.",
    ],
    "UNKNOWN": [
        "{name} reside na Rua das Flores, em Lisboa.",
        "{name} assinou o contrato em 12/05/2021.",
        "{name} deslocou-se ao Porto.",
        "{name} apresentou o cartão de cidadão.",
        "{name} trabalha na empresa Alfa Lda.",
    ],
}


def generate_examples():
    examples = []

    for label, templates in TEMPLATES.items():
        for template in templates:
            for name in NAMES:
                text = template.format(name=name)
                marked_text = text.replace(name, f"[ENTITY] {name} [/ENTITY]", 1)
                examples.append({
                    "text": marked_text,
                    "entity": name,
                    "label": label
                })

    random.shuffle(examples)
    return examples


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    examples = generate_examples()

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"Generated {len(examples)} examples")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()