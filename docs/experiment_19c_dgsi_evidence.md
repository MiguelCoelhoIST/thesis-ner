# 19c — fontes DGSI e identificadores visualmente ambíguos

O utilizador confirmou que as três pendências GOLD vêm de dois acórdãos e que os contextos aparecem integralmente nos dois textos obtidos. No g09, a validação parou em `external_source_identity_not_verified`. Não se leram os documentos privados neste workspace; as identidades reais não são reproduzidas aqui.

## Causa e correção

O parser canónico exige ano de 2–4 dígitos e um dígito antes do código de tribunal, depois do ponto. Letras nessas posições são rejeitadas. Acrescentar `Processo:` não torna o token válido. Existia também uma limitação de layout: valor numa linha seguinte, comum em cópias/tabelas DGSI, não era reconhecido.

O parser passa a aceitar label/valor em linhas consecutivas, NBSP/BOM e variantes do label; guarda o token exibido, offsets exatos e códigos de rejeição em `unparsed_header_evidence`. **Não troca S por 5**, não flexibiliza a gramática canónica e não promove citações do corpo: a procura termina em Sumário/Texto Integral. O sufixo da decisão é preservado, separadamente do grupo processual. O limite normal de cabeçalho continua 40 linhas/3000 caracteres; apenas a leitura explícita de captura DGSI permite 120 linhas/10000 caracteres, sempre antes do corpo.

Para uma cópia cujo ID permaneça não-canónico, um recibo privado pode confirmar identidade a partir de uma captura oficial local. Isto é uma nova modalidade de evidência dentro de `validate_decision`, não um bypass. São exigidos:

- hash dos bytes e do texto extraído da cópia, sem a modificar;
- captura HTML/MHTML/TXT local verificada por hash e com um único ID canónico inequívoco no campo Processo;
- URL DGSI `jstj.nsf/...?...OpenDocument`, sem credenciais/hosts alternativos; o UNID identifica a decisão, não a família processual;
- origem da página guardada (MHTML Content-Location, metadata canonical/og:url ou saved-from-url) **ou** concordância do URL com a referência GOLD congelada; um link arbitrário no corpo não prova origem;
- contexto protegido presente tanto na cópia como na captura, fingerprints da referência e confirmação humana explícita da discrepância;
- inexistência de uma identidade canónica contraditória na cópia/filename. Os valores originais ambíguos continuam no recibo, sem renumeração silenciosa.

HTML é lido offline, sem executar scripts/carregar recursos; MHTML usa apenas a biblioteca padrão e exige um único documento HTML. Scripts/head não entram no texto visível. Não há requests, novas APIs, downloads ou dependências. Hashes provam integridade de artefactos locais, **não uma assinatura do servidor**; o revisor confirma a ligação à fonte oficial.

Se a captura também tiver um ID não-canónico, não se consegue confirmar uma correção numérica: a ferramenta bloqueia. Obter evidência oficial adicional; não editar os textos ou inserir um número presumido para satisfazer o parser. Um TXT sem metadata de origem só é aceite se o URL da referência congelada confirmar a mesma decisão; caso contrário guardar uma captura com origem, por exemplo MHTML.

## Um comando para preparar a nova prova privada

Na raiz do checkout g09, com `venv-ner` ativo e Git limpo/atualizado:

```bash
python -u src/annotation/prepare_dgsi_adjudication_19c.py \
  --selection-manifest data/raw/experiment_19c_pilot01/selection_manifest.json \
  --output-dir data/raw/experiment_19c_dgsi_evidence01
```

O comando pede o caminho do JSON privado de decisões que já foi criado. Pode ser fornecido diretamente com `--decisions`. Os caminhos dos dois textos são lidos desse ficheiro; as fontes e fingerprints existentes precisam de continuar intactos. Não é necessário escrever os três IDs das referências nem refazer o diagnóstico.

A ferramenta pede o revisor/fundamento e, uma vez por fonte, a captura oficial local, o URL e `CONFIRMO`, após consulta privada da página. Capturas e textos têm de estar em `data/raw/` no armazenamento autorizado. Os prompts não mostram nomes/IDs; o que é introduzido no terminal é privado, não material para partilha. Para formatos inválidos/ambíguos ou dados desatualizados há erro de código fixo, sem dumps de conteúdo.

Saídas novas, com umask 077:

- `identity_XX_PRIVATE.json`: recibos, valores originais/confirmados, URL e hashes.
- `protection_decisions_PRIVATE.json`: novas decisões vinculadas às provas; o JSON anterior não é sobrescrito.
- `validation_PRIVATE.json`: verificação de todas as referências e grupos; privado.
- Se houver ligação positiva ao corpus, `reservation_XX_PRIVATE.json`: pacote que reserva todos os documentos correspondentes e propaga a reserva por processos/aliases.

Se a identidade confirmada aparecer no corpus, a ferramenta **não a declara externa**: produz reserva documental e `validate_decision` recusa omissões de sobreposições conhecidas. Fora do corpus, continuam obrigatórias a verificação de contexto, a disjunção de raiz/hash e as restantes proteções. Só avançar quando stdout indicar zero pendências; não alterar selection_complete, remover referências ou editar NER/GOLD.

## Seleção final e preflight

Escolher diretórios novos; não reutilizar saídas que já existam:

```bash
python -u src/annotation/prepare_stj_pilot_19c.py \
  --input data/raw/experiment_19b_ner_full_15216_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_ner_full_15216_manifest.json \
  --gold data/eval/roles_eval_real_candidates_v1.jsonl \
  --pilot-sources data/raw/experiment_19a_candidates_v4_smoke10.jsonl \
  --protection-decisions data/raw/experiment_19c_dgsi_evidence01/protection_decisions_PRIVATE.json \
  --output-dir data/raw/experiment_19c_pilot03 --seed 42
```

Continuar apenas com selection_complete=true e 30 selecionados, após inspeção privada do manifesto. Não há marcação gold/human-validated ou autorização de treino. O preflight Qwen mantém o [protocolo existente](experiment_19c_qwen_pilot.md), com dados/código/checkpoint iguais entre jobs. Verificar recursos atuais antes de submeter; não executar Qwen no login:

```bash
sinfo -N -o '%N %P %t %G'
scontrol show partition hlt_msc
scontrol show node g06
# QWEN_REVISION: commit imutável local previamente verificado; sem downloads.
test -n "$QWEN_REVISION"
PRE_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist=g06 --gres=gpu:1 \
  scripts/slurm/run_qwen3_19c_pilot.sbatch preflight data/raw/experiment_19c_pilot03)
PRE_JOB=${PRE_JOB%%;*}
sacct -j "$PRE_JOB" --format=JobID,State,ExitCode,Elapsed
```

Esperar COMPLETED/0:0 e conferir preflight_passed, modelo, GPU e os 30 comprimentos em `data/raw/experiment_19c_preflight_${PRE_JOB}/run.json`. Depois, se autorizado e sem alterações de dados/código:

```bash
sbatch --partition=hlt_msc --nodelist=g06 --gres=gpu:1 \
  scripts/slurm/run_qwen3_19c_pilot.sbatch pilot data/raw/experiment_19c_pilot03 \
  "data/raw/experiment_19c_preflight_${PRE_JOB}/run.json"
```

A ferramenta foi testada com três referências e dois documentos **inventados**, chegando a zero pendências e seleção de 30 sem modificar inputs. Não se executou o wizard sobre os originais reais nem se confirmou o desbloqueio no INESC nesta sessão. Corpus, GOLD, revisões e `silver.spacy` permanecem intocados.

Validação local: **181 testes**, sucesso, **1 integração opcional omitida**, incluindo **13 novos** de cabeçalhos/capturas/recibos e wizard. Não substituem validação dos artefactos reais.
