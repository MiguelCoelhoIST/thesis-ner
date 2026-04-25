import json
import random
from typing import List, Tuple, Dict

random.seed(42)

PEOPLE = [
    "João Silva", "Pedro Costa", "Maria Ferreira", "Ana Martins", "Carlos Mendes",
    "Sofia Almeida", "Rui Lopes", "José Oliveira", "Carla Sousa", "Inês Costa",
    "Manuel Ferreira", "Paulo Rocha", "Teresa Gomes", "Helena Cruz", "Tiago Fernandes",
    "Luís Matos", "Marta Ribeiro", "Maria dos Santos", "Ricardo Alves", "Bruno Fernandes"
]

SHORT_PEOPLE = [
    "João P. Silva", "M. Ferreira", "Ana C. Martins", "Rui A. Lopes"
]

ROLES = [
    "testemunha", "arguido", "arguida", "réu", "ré",
    "ofendida", "vítima", "denunciante", "assistente", "relator"
]

STREETS = [
    "Rua das Flores", "Avenida da Liberdade", "Travessa do Sol", "Praceta das Oliveiras",
    "Rua Nova", "Alameda Verde", "Rua de São Bento", "Rua 5 de Outubro",
    "Rua do Pinhal", "Largo do Carmo", "Rua da Alegria"
]

CITIES = ["Lisboa", "Porto", "Braga", "Coimbra", "Faro", "Setúbal", "Aveiro", "Viseu"]
POSTALS = ["1200-450", "4000-123", "4700-220", "3000-150", "8000-210", "2900-410"]
COMPANIES = [
    "XPTO Lda.", "AlfaBeta S.A.", "Delta Consulting, Unipessoal Lda.",
    "Oficina Central, Lda.", "Silva & Filhos, S.A.", "TechVista Lda."
]
DATES = ["01/01/2020", "12/03/1985", "7 de maio de 2021", "03-11-2022", "14 de fevereiro de 2019"]
NIFS = ["123456789", "509876543", "245678901", "987654321"]
CCS = ["14567890 ZX5", "12345678 AB1", "99887766 XY2"]
PASSPORTS = ["X1234567", "P9988776", "L5544332"]
IBANS = ["PT50000201231234567890154", "PT50001000001234567890133"]
PLATES = ["AA-12-BB", "12-AB-34", "77-ZZ-10"]
CONTRACTS = ["12345", "54321", "98765", "2024/11", "A-7788"]

LABEL_PER = "PER"
LABEL_ORG = "ORG"
LABEL_LOC = "LOC"
LABEL_DAT = "DAT"
LABEL_IDP = "IDP"
LABEL_ROLE = "LEGROLE"

def add_entity(text: str, entities: List[Tuple[int, int, str]], value: str, label: str):
    start = text.find(value)
    if start == -1:
        raise ValueError(f"Value not found: {value!r} in {text!r}")
    entities.append((start, start + len(value), label))

def make_address(street: str, city: str) -> str:
    num = random.randint(1, 150)
    postal = random.choice(POSTALS)
    patterns = [
        f"{street}, n.º {num}, {city}",
        f"{street}, {postal} {city}",
        f"{street}, n.º {num}, 2.º Esq., {city}",
        f"{street}, n.º {num}, {postal} {city}",
    ]
    return random.choice(patterns)

def template_statement():
    person = random.choice(PEOPLE)
    role = random.choice(ROLES)
    text = f"A {role} {person} declarou em tribunal."
    entities = []
    add_entity(text, entities, role, LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    return {"text": text, "entities": entities}

def template_condemnation():
    person = random.choice(PEOPLE)
    role = random.choice(["arguido", "arguida", "réu", "ré"])
    text = f"O {role} {person} foi condenado."
    if role in ["arguida", "ré"]:
        text = f"A {role} {person} foi condenada."
    entities = []
    add_entity(text, entities, role, LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    return {"text": text, "entities": entities}

def template_residence():
    person = random.choice(PEOPLE)
    address = make_address(random.choice(STREETS), random.choice(CITIES))
    text = f"{person} reside na {address}."
    entities = []
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, address, LABEL_LOC)
    return {"text": text, "entities": entities}

def template_birth_and_address():
    person = random.choice(PEOPLE)
    date = random.choice(DATES)
    address = make_address(random.choice(STREETS), random.choice(CITIES))
    text = f"{person} nasceu em {date} e vive atualmente na {address}."
    entities = []
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, date, LABEL_DAT)
    add_entity(text, entities, address, LABEL_LOC)
    return {"text": text, "entities": entities}

def template_company():
    company = random.choice(COMPANIES)
    city = random.choice(CITIES)
    text = f"A empresa {company} tem sede em {city}."
    entities = []
    add_entity(text, entities, company, LABEL_ORG)
    add_entity(text, entities, city, LABEL_LOC)
    return {"text": text, "entities": entities}

def template_company_address():
    company = random.choice(COMPANIES)
    address = make_address(random.choice(STREETS), random.choice(CITIES))
    text = f"A sociedade {company} indicou como sede a {address}."
    entities = []
    add_entity(text, entities, company, LABEL_ORG)
    add_entity(text, entities, address, LABEL_LOC)
    return {"text": text, "entities": entities}

def template_contract():
    person = random.choice(PEOPLE)
    contract = random.choice(CONTRACTS)
    date = random.choice(DATES)
    text = f"O contrato n.º {contract} foi assinado por {person} em {date}."
    entities = []
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, date, LABEL_DAT)
    return {"text": text, "entities": entities}

def template_nif():
    role = random.choice(ROLES)
    person = random.choice(PEOPLE)
    nif = random.choice(NIFS)
    text = f"A {role} {person} apresentou o NIF {nif}."
    entities = []
    add_entity(text, entities, role, LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, nif, LABEL_IDP)
    return {"text": text, "entities": entities}

def template_cc():
    role = random.choice(ROLES)
    person = random.choice(PEOPLE)
    cc = random.choice(CCS)
    text = f"A {role} {person} indicou o cartão de cidadão {cc}."
    entities = []
    add_entity(text, entities, role, LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, cc, LABEL_IDP)
    return {"text": text, "entities": entities}

def template_passport():
    role = random.choice(ROLES)
    person = random.choice(PEOPLE)
    passport = random.choice(PASSPORTS)
    text = f"O {role} {person} forneceu o passaporte {passport}."
    entities = []
    add_entity(text, entities, role, LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, passport, LABEL_IDP)
    return {"text": text, "entities": entities}

def template_iban():
    role = random.choice(ROLES)
    person = random.choice(PEOPLE)
    iban = random.choice(IBANS)
    article = "A"
    text = f"{article} {role} {person} juntou o IBAN {iban}."
    entities = []
    add_entity(text, entities, role, LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, iban, LABEL_IDP)
    return {"text": text, "entities": entities}

def template_plate():
    plate = random.choice(PLATES)
    address = f"{random.choice(STREETS)}, {random.choice(CITIES)}"
    text = f"Foi identificado o veículo {plate} junto da {address}."
    entities = []
    add_entity(text, entities, plate, LABEL_IDP)
    add_entity(text, entities, address, LABEL_LOC)
    return {"text": text, "entities": entities}

def template_title_edge():
    person = random.choice(PEOPLE)
    city = random.choice(CITIES)
    text = f"A testemunha Eng. {person} compareceu no Tribunal Judicial de {city}."
    entities = []
    add_entity(text, entities, "testemunha", LABEL_ROLE)
    add_entity(text, entities, person, LABEL_PER)
    add_entity(text, entities, f"Tribunal Judicial de {city}", LABEL_ORG)
    return {"text": text, "entities": entities}

def template_short_name_edge():
    person1 = random.choice(SHORT_PEOPLE)
    person2 = random.choice(PEOPLE)
    city = random.choice(CITIES)
    text = f"A testemunha {person1} declarou que viu {person2} em {city}."
    entities = []
    add_entity(text, entities, "testemunha", LABEL_ROLE)
    add_entity(text, entities, person1, LABEL_PER)
    add_entity(text, entities, person2, LABEL_PER)
    add_entity(text, entities, city, LABEL_LOC)
    return {"text": text, "entities": entities}

TEMPLATES = [
    template_statement,
    template_condemnation,
    template_residence,
    template_birth_and_address,
    template_company,
    template_company_address,
    template_contract,
    template_nif,
    template_cc,
    template_passport,
    template_iban,
    template_plate,
    template_title_edge,
    template_short_name_edge,
]

def generate_dataset(n=100):
    return [random.choice(TEMPLATES)() for _ in range(n)]

def save_jsonl(data, path):
    with open(path, "w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    dataset = generate_dataset(200)
    save_jsonl(dataset, "data/processed/synthetic_legal_ner.jsonl")
    print(f"Saved {len(dataset)} examples.")