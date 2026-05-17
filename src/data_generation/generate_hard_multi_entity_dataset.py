import json
import random
from pathlib import Path

OUTPUT_PATH = Path("data/processed/roles_hard_multi_entity.jsonl")

names = [
    "João Martins",
    "Ana Silva",
    "Carlos Mendes",
    "Maria Ferreira",
    "Luís Matos",
    "Pedro Costa",
    "Carla Sousa",
    "António Ribeiro",
]

templates = [
    {
        "text": "O arguido {name1} foi ouvido e a testemunha [ENTITY] {name2} [/ENTITY] prestou declarações.",
        "label": "TESTEMUNHA",
    },
    {
        "text": "A testemunha {name1} declarou em tribunal contra o arguido [ENTITY] {name2} [/ENTITY].",
        "label": "ARGUIDO",
    },
    {
        "text": "O relator {name1} proferiu decisão após ouvir a testemunha [ENTITY] {name2} [/ENTITY].",
        "label": "TESTEMUNHA",
    },
    {
        "text": "A testemunha {name1} identificou o réu [ENTITY] {name2} [/ENTITY].",
        "label": "REU",
    },
    {
        "text": "O réu {name1} foi representado pela mandatária [ENTITY] {name2} [/ENTITY].",
        "label": "UNKNOWN",
    },
    {
        "text": "O arguido {name1} foi identificado pelo relator [ENTITY] {name2} [/ENTITY].",
        "label": "RELATOR",
    },
]

NUM_EXAMPLES = 500


def generate_example():
    template = random.choice(templates)

    name1 = random.choice(names)
    name2 = random.choice(names)

    while name1 == name2:
        name2 = random.choice(names)

    text = template["text"].format(
        name1=name1,
        name2=name2,
    )

    return {
        "text": text,
        "entity": name2,
        "label": template["label"],
    }


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for _ in range(NUM_EXAMPLES):
            example = generate_example()
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

    print(f"Generated {NUM_EXAMPLES} examples")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()