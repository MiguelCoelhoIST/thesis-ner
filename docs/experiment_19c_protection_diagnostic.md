# Experiência 19c — diagnóstico e adjudicação de referências protegidas

O utilizador comunicou uma execução no g09: seleção incompleta, zero selecionados, 111 referências verificadas, 108 resolvidas, três pendentes, 15 grupos bloqueados, zero chamadas LLM. **O manifesto privado não foi consultado neste workspace**; não se afirma a origem ou causa efetiva das três. Esta ferramenta deve ser executada no INESC. Sem NER, Qwen, APIs ou alteração de datasets.

## Condição exata do bloqueio original

Em `assess_protection()`, uma referência ficava pendente se não tivesse nenhuma raiz de `identity_roots(ref)`, nenhum documento associado e nenhuma decisão aceite. As raízes vêm de process_number, decision_id, grupos/candidatos e evidência de cabeçalho/filename; não de papéis jurídicos nem de referências arbitrárias no corpo. Um documento era associado por raiz processual, hash exato do texto-fonte, par exato source_file/source_document_id em aliases ou contenção literal do contexto após casefold/whitespace, com pelo menos cinco palavras. Uma raiz normalizável sem correspondência no inventário já era considerada identificada, sem reservar documentos. Identificação não é certificação de independência.

As referências são indexadas por conjunto protegido mais ID interno, preservando os 50 GOLD e os 61 registos de fontes do piloto. Qualquer pendência faz `select_pilot()` devolver seleção vazia **antes da amostragem**. Não se alterou essa gate. Os 111 checks e todas as pendências continuam representados nas novas auditorias.

## Diagnóstico público e privado

[diagnose_pilot_protection_19c.py](../src/annotation/diagnose_pilot_protection_19c.py) lê o manifesto da seleção bloqueada, verifica todos os fingerprints guardados, o bundle NER completo, os dois ficheiros protegidos congelados e as fontes originais. Compara as pendências registadas com os inputs e identifica a origem por código GOLD/HUMAN_PILOT.

O ficheiro partilhável e stdout contêm apenas versões/códigos fixos, contagens e **HMAC-SHA256** de referências/documentos, com uma chave aleatória de 256 bits privada. Não usam SHA simples de IDs adivinháveis. Não incluem IDs originais, hashes brutos, processos, caminhos privados, nomes ou excertos. O mapeamento, chave, referências completas e propostas de revisão ficam exclusivamente em outputs privados ignorados. Não partilhar ficheiros PRIVATE nem a chave. Tokens mantêm-se com a mesma chave; uma nova chave gera tokens diferentes. Para comparar duas execuções, `--hmac-key` aceita a chave privada anterior em `data/raw/`.

Códigos distinguem metadata ausente de não normalizável, hash ausente/sem associação, par documental incompleto/sem associação, ausência de contenção literal e contexto curto. Uma pesquisa sem resultado **não** produz um código de ausência comprovada no corpus. Sugestões por sobreposição de palavras no contexto têm código `WEAK_CONTENT_CANDIDATES_NOT_PROOF`; são limitadas a cinco documentos por referência, não resolvem a pendência nem atribuem papéis.

## Reconciliação verificável, só com reservas positivas

[role_reference_provenance.py](../src/annotation/role_reference_provenance.py) é usado pelo diagnóstico e pela seleção, com normalização `19c-formatting-v1`. Acrescenta:

- correspondência exata de document_id por hash;
- contenção do contexto completo após NFC, casefold, whitespace, remoção de soft hyphen/zero-width/BOM, união de palavras hifenizadas por quebra de linha e normalização de aspas tipográficas;
- variante de formato de process_number semelhante a filename **apenas se corresponder positivamente a uma raiz existente do inventário**.

A nova contenção exige pelo menos oito palavras e 40 letras. Não remove acentos, reordena palavras, troca pessoas, inventa offsets ou resolve identidade por similaridade. **Todos** os documentos correspondentes são reservados, mesmo se houver vários; os grupos/aliases relacionados continuam bloqueados. Métodos, versão, fingerprints e documentos ficam na auditoria privada. Uma reserva conservadora não afirma identidade jurídica nem transforma a referência em exemplo seguro para treino. Correspondências literais antigas continuam válidas; referências sem evidência suficiente continuam pendentes. Se a reconciliação bastar, repetir a seleção sem adjudicação manual e com novo output.

## Adjudicação privada com evidência vinculada

O diagnóstico gera `adjudication_template_PRIVATE.json` apenas para casos ainda não reconciliados. Cada entrada tem o ID privado correto, `reference_sha256`, fingerprint do inventário, `human_confirmed=false` e campos vazios de reviewer/reason/evidence. Não confirmar automaticamente nem substituir por uma lista vazia. O mecanismo v2 recusa o formato antigo composto apenas por checkbox/justificação.

Decisões exigem confirmação humana explícita, revisor, fundamento, fingerprints atuais e um ficheiro de evidência local em `data/raw/`, conferido por SHA-256. Há duas vias:

1. **Reservar documentos:** após verificar o vínculo de proveniência, preencher document_ids. A evidência `reservation_packet` é um JSON privado com reference_sha256, os mesmos document_ids e document_source_hashes (mapa ID → source_text_sha256 do inventário). O pacote regista a adjudicação humana vinculada a fontes verificáveis; hashes provam integridade, **não a correção semântica do vínculo**. Rever a referência e os originais correspondentes, não escolher um candidato só por aparecer na pesquisa. Todos os grupos indicados são excluídos; não se apaga evidência já detetada.
2. **Fonte externa comprovada:** `excluded_from_corpus=true` exige evidência `external_source`, apontando para o acórdão original local, não só uma nota declarativa. O leitor existente extrai o texto; o contexto protegido completo normalizado tem de estar presente e suficientemente longo. O cabeçalho tem de estabelecer uma só identidade sem conflito de filename; o texto-fonte e a raiz não podem coincidir com nenhum documento/raiz/alias conhecido do inventário. Havendo correspondência interna, ID externo conflitante, fonte sem cabeçalho ou contexto inexistente, a decisão falha. Grupos de identidade desconhecida do corpus continuam excluídos pela seleção. Ausência de match, por si só, nunca basta para esta opção.

Exemplo estrutural, com placeholders e sem dados reais:

```json
{
  "gold:ID_PRIVADO": {
    "human_confirmed": true,
    "reviewer": "REVISOR_LOCAL",
    "reason": "Fundamento verificado privadamente",
    "reference_sha256": "HASH_GERADO_PELO_DIAGNOSTICO",
    "inventory_fingerprint": "HASH_GERADO_PELO_DIAGNOSTICO",
    "document_ids": ["doc_HASH_VERIFICADO"],
    "evidence": [{"kind": "reservation_packet", "path": "data/raw/packet_PRIVATE.json", "sha256": "HASH_DO_PACOTE"}]
  }
}
```

Para fonte externa, usar document_ids vazio/ausente, excluded_from_corpus=true e evidence.kind=external_source. Se o ficheiro contiver vários documentos, indicar também evidence.source_document_id. Uma adjudicação antiga/stale, evidência alterada, ref/inventário diferentes ou decisão para um ID desconhecido é erro. Os hashes dos ficheiros de evidência passam também para o novo manifesto de seleção e são revalidados antes do Qwen. Nenhuma adjudicação altera as labels GOLD, offsets, textos ou human_validated.

## Comandos no g09

Na raiz do checkout remoto, depois de verificar que não há alterações locais a preservar:

```bash
cd ~/thesis-ner
git status --short
git pull --ff-only origin develop
source venv-ner/bin/activate
python -u src/annotation/diagnose_pilot_protection_19c.py \
  --selection-manifest data/raw/experiment_19c_pilot01/selection_manifest.json \
  --output-dir data/raw/experiment_19c_protection_diag01
```

Outputs novos, sem sobrescrita:

- `shareable_diagnostic.json`: único ficheiro destinado a partilha após conferir o formato; stdout corresponde ao mesmo JSON.
- `reference_evidence_PRIVATE.json`: IDs originais, records e associação dos tokens, métodos e candidatos; consultar apenas localmente.
- `adjudication_template_PRIVATE.json`: pendências restantes, não aprovadas.
- `token_key_PRIVATE.bin`: chave; não partilhar/publicar.

Só o primeiro pode ser apresentado sem o conteúdo privado:

```bash
cat data/raw/experiment_19c_protection_diag01/shareable_diagnostic.json
```

Se `manual_provenance_required=0`, a reconciliação positiva já permite tentar nova seleção; se não, adjudicar as entradas restantes antes. Preservar o template e guardar a versão preenchida como `data/raw/experiment_19c_protection_decisions_v1_PRIVATE.json`. Para obter os hashes de ficheiros locais sem imprimir o conteúdo, usar `sha256sum` no INESC; guardar nomes/hashes das fontes apenas na decisão privada. Os document_source_hashes vêm do `_documents.jsonl` privado do job 15216. A chave de referência e o fingerprint do inventário já estão no template; não os substituir manualmente por outros dados.

Nova seleção, sempre para um diretório novo:

```bash
python -u src/annotation/prepare_stj_pilot_19c.py \
  --input data/raw/experiment_19b_ner_full_15216_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_ner_full_15216_manifest.json \
  --gold data/eval/roles_eval_real_candidates_v1.jsonl \
  --pilot-sources data/raw/experiment_19a_candidates_v4_smoke10.jsonl \
  --output-dir data/raw/experiment_19c_pilot02 --seed 42
```

Quando forem necessárias adjudicações, acrescentar ao comando:

```bash
python -u src/annotation/prepare_stj_pilot_19c.py \
  --input data/raw/experiment_19b_ner_full_15216_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_ner_full_15216_manifest.json \
  --gold data/eval/roles_eval_real_candidates_v1.jsonl \
  --pilot-sources data/raw/experiment_19a_candidates_v4_smoke10.jsonl \
  --protection-decisions data/raw/experiment_19c_protection_decisions_v1_PRIVATE.json \
  --output-dir data/raw/experiment_19c_pilot02 --seed 42
```

Não repetir o comando sobre um diretório já existente. A gate só passa com zero pendências e 30 grupos elegíveis/variados após todas as exclusões. Não mudar selection_complete nem remover referências. Se persistir bloqueio, partilhar apenas o relatório público; manter a seleção suspensa. O próximo passo Qwen continua a exigir os gates/preflight do [protocolo do piloto](experiment_19c_qwen_pilot.md).

Os testes são sintéticos: reconciliação positiva permite selecionar 30 num corpus inventado, ausência/candidatos fracos continuam bloqueados, decisões sem evidência/stale/conflitantes falham, e stdout/JSON público não contêm sentinelas privadas. Não demonstram que as três referências reais tenham sido resolvidas. Não se executou este diagnóstico no INESC nesta sessão.

Suite local: **168 testes**, sucesso, **1 integração opcional omitida**; **16 novos** de diagnóstico/proveniência. Não foram alterados os 24.467 registos, GOLD, revisões, modelos ou `silver.spacy`.
