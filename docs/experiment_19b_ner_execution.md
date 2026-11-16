# Experiência 19b — execução NER integral via Slurm

Revisto em **16-11-2026**. **Etapa concluída**, segundo confirmação do utilizador: job **15216, COMPLETED, ExitCode 0:0**, 388 documentos auditados, 191/191 textos distintos processados, 24.467 PER aceites, 24.977 previsões PER brutas, `inventory_complete=True`, `NER_executed=True`, `LLM_calls=0`. São spans NER, não labels jurídicas. Os relatórios dos jobs 15209/15215/15216 permanecem apenas no g09 e não foram consultados nesta consolidação.

Os comandos seguintes documentam uma eventual repetição técnica, **não um próximo passo nem autorização para voltar a executar NER agora**. Preservar os outputs do job 15216 e preparar a anotação posteriormente. Não criar novas amostras por papel nem executar Qwen, treino ou anotação externa nesta revisão.

## Confirmação do caminho de execução

- O preparador lê as fontes originais, extrai proveniência e agrupa por hash do texto extraído. Por omissão não precisa de auditorias ou candidatos antigos. Cada um dos 191 conteúdos tem uma passagem NER, com janelas sobrepostas; as 388 versões e evidências continuam em `*_documents.jsonl`. Os hashes dos inputs são registados.
- As janelas cobrem o texto inteiro e não dependem de âncoras. Não há quota de 60/40/430 nem classificação lexical. Mesma pessoa em posições diferentes continua a produzir ocorrências diferentes.
- `*_mentions.jsonl` contém os PER aceites pelos filtros atuais, com contexto, offsets documentais/locais e IDs estáveis por hash/posição. `*_ner_predictions.jsonl` conserva **todas as previsões**, incluindo PER filtradas, outras classes NER e janelas de origem. PER com offsets válidos recebem também contexto e mention_id, mesmo quando filtradas. Não se perde a possibilidade de rever falsos negativos dos filtros. O modelo pode omitir pessoas: cobertura integral não certifica recall perfeito.
- Em `--run-ner`, não se escreve outro `known_mentions_PARTIAL.jsonl`. O smoke é apenas o teste técnico solicitado. Há heartbeat por dez segundos e contagem de documentos/janelas/menções. O manifesto guarda parâmetros, tempos, metadados do modelo e hashes dos inputs/scripts.
- Benchmarks e datasets existentes não são modificados; gold/piloto só são lidos quando fornecidos explicitamente para exclusão. Outputs têm nomes novos por job e recusam sobrescrita. Não há suggested_label nas menções futuras nem labels jurídicas atribuídas pelo NER. Tudo permanece privado em `data/raw/`.
- O commit **fc069e15** corrige a expansão WordPiece: o striding treinado usa 128 tokens spaCy/stride 96, mas o BERT tem 512 posições e o tokenizer declara um limite sentinela excessivo. O guard conta tokens especiais e subdivide apenas janelas exteriores excessivas, mantendo cobertura/offsets sem truncagem. Antes da inferência, até o smoke verifica a tokenização dos **191 textos**; os manifestos guardam limites, subdivisões e hash do guard. Isto não garante recall perfeito.

## Taxonomia e anotações futuras

A versão operacional é [role_taxonomy_v2.json](../config/role_taxonomy_v2.json): ARGUIDO, REU, AUTOR, REQUERENTE, RECORRENTE, RECORRIDO, TESTEMUNHA, RELATOR, REFERENCE, UNKNOWN. O ficheiro histórico de nove classes fica intacto para reproduzir experiências anteriores.

O task/schema produzido permite `labels` como lista multi-label, com evidência e âmbito por papel. `other_roles` guarda designação literal, quote e âmbito de papéis fora da lista, sem os transformar automaticamente em novas classes nem perder essa informação. UNKNOWN significa ausência dos nove papéis específicos, não ambiguidade; um papel fora da lista pode ser preservado em other_roles. REFERENCE não implica autorização de preservar identidades.

Guardar sempre as labels finas e a resposta original do anotador. A comparação agrupada deriva depois do mesmo dataset/splits através do mapper existente, usando `--config config/role_taxonomy_v2.json`. REFERENCE mantém uma classe própria na agregação; a configuração pode mudar sem nova anotação fina. Não substituir as labels finas pelo resultado agrupado. Anotações automáticas serão SILVER, nunca human_validated=true.

## Antes de executar: checkout remoto

Os comandos pressupõem que o checkout remoto tem os ficheiros revistos. Não houve transferência automática. Confirmar especialmente:

- `src/data/prepare_stj_corpus_inventory.py` e o detetor existente com `prediction_sink`;
- `src/utils/transformer_length_guard.py`;
- helpers já usados em `src/annotation/prepare_role_annotation_batch.py` e `src/annotation/export_external_annotation.py`;
- `config/role_taxonomy_v2.json`;
- `scripts/slurm/run_stj_inventory_19b.sbatch`.

Não sincronizar modelos ou dados privados pelo Git. Não sobrescrever alterações remotas sem inspeção. Desde **86ecf19**, ficheiros antigos da 19a não são pré-condição: `--audit`, `--candidates`, `--pilot`, `--gold` e `--reuse-privacy-map` são referências opcionais e explícitas. Se fornecidos, têm de existir e passar as verificações; não são ignorados silenciosamente. A ausência de checks opcionais gold/piloto não prova ausência de leakage e fica por resolver antes dos splits.

## 1. Ligar e verificar Slurm

Executar manualmente, definindo previamente `INESC_USER` com o seu utilizador institucional. Não guardar passwords, tokens ou chaves neste ficheiro:

```bash
ssh g09.hlt.inesc-id.pt -l "$INESC_USER"
cd ~/thesis-ner
mkdir -p data/raw results

sinfo -N -o '%N %P %t %G'
# g09 é o ponto de acesso SSH; confirmar o nó de execução autorizado.
NER_NODE=g06
scontrol show node "$NER_NODE"
scontrol show partition hlt_msc

test -x venv-ner/bin/python
test -f models/eduardo_extended_model/config.cfg
test -f config/role_taxonomy_v2.json
test -f scripts/slurm/run_stj_inventory_19b.sbatch
test -f src/utils/transformer_length_guard.py
test -d data/raw/iris/naoanomimizados_txt
source venv-ner/bin/activate
python src/data/prepare_stj_corpus_inventory.py --help
bash -n scripts/slurm/run_stj_inventory_19b.sbatch
```

`hlt_msc` é a partição dos scripts históricos, **não uma disponibilidade verificada nesta sessão**. `g06` é o nó referido nas execuções anteriores, não uma reserva atual. Só avançar numa nova execução autorizada se `$NER_NODE` aparecer na partição com recursos aplicáveis. Caso contrário, confirmar a partição/NodeName; não executar diretamente na GPU nem escolher outro nó automaticamente.

A tentativa SSH da preparação antiga falhou no DNS; isso não descreve a disponibilidade atual. Nesta consolidação não se contactou o servidor. Os testes locais validam código e bash, não o scheduler remoto.

## 2. Submeter smoke de três documentos

Ainda na raiz do repositório remoto:

```bash
SMOKE_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist="$NER_NODE" --gres=gpu:1 scripts/slurm/run_stj_inventory_19b.sbatch smoke)
SMOKE_JOB=${SMOKE_JOB%%;*}
echo "SMOKE_JOB=$SMOKE_JOB"
squeue -j "$SMOKE_JOB"
```

O wrapper ativa `venv-ner`, exige job Slurm/GPU atribuída, mantém `CUDA_VISIBLE_DEVICES` do scheduler e chama `--gpu-id 0`. Não exportar CUDA_VISIBLE_DEVICES=3. Recursos pedidos: uma GPU, quatro CPUs, 32 GB RAM, até duas horas. Não há downloads, Qwen ou serviços externos.

Para acompanhar e verificar após terminar:

```bash
tail -f "data/raw/stj_19b_ner_${SMOKE_JOB}.out"
# Ctrl+C sai apenas do tail, não cancela o job.
sacct -j "$SMOKE_JOB" --format=JobID,State,ExitCode,Elapsed,MaxRSS
SMOKE_MANIFEST="data/raw/experiment_19b_ner_smoke_${SMOKE_JOB}_manifest.json"
python -c 'import json,sys; m=json.load(open(sys.argv[1])); print(json.dumps(m["summary"],indent=2))' "$SMOKE_MANIFEST"
```

Confirmar COMPLETED/ExitCode 0, stdout `NER device: GPU 0`, universo unique_texts=191, NER_documents_processed=3, accepted_mentions_this_run positivo e ausência de falhas. Inspecionar as contagens de rejeições/offsets no agregado; a gate automática não certifica a qualidade jurídica/NER. O resumo do smoke deve ter inventory_complete=false porque só três dos 191 textos foram inferidos.

Confirmar também `transformer_length_validation.validated=true`, `documents=191` e `maximum_safe_wordpieces<=effective_limit` (512 no BERT local inspecionado). Um manifesto anterior à correção/validação integral de tokenização não serve para um novo full.

## 3. Submeter o corpus completo depois do smoke

Sem alterar código/inputs entre os jobs:

```bash
FULL_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist="$NER_NODE" --gres=gpu:1 scripts/slurm/run_stj_inventory_19b.sbatch full "$SMOKE_MANIFEST")
FULL_JOB=${FULL_JOB%%;*}
echo "FULL_JOB=$FULL_JOB"
squeue -j "$FULL_JOB"
tail -f "data/raw/stj_19b_ner_${FULL_JOB}.out"
```

O wrapper full valida o manifesto do smoke (três documentos, menções positivas, mesmo universo, código, guard, hashes dos inputs e preflight WordPiece dos 191 textos), depois executa **sem --max-documents**. Não inicia a passagem full se a gate falhar. Não há novo inventário recuperado parcial. O teste de três documentos é repetido dentro da passagem integral para produzir uma saída uniforme; os ficheiros de smoke não são concatenados ao resultado final.

Após terminar:

```bash
sacct -j "$FULL_JOB" --format=JobID,State,ExitCode,Elapsed,MaxRSS
FULL_PREFIX="data/raw/experiment_19b_ner_full_${FULL_JOB}"
python -c 'import json,sys; s=json.load(open(sys.argv[1]))["summary"]; assert s["inventory_complete"] and s["NER_documents_processed"]==191 and s["unique_texts"]==191 and s["audited_documents"]==388; print(json.dumps(s,indent=2))' "${FULL_PREFIX}_manifest.json"
```

Saídas: `${FULL_PREFIX}_mentions.jsonl`, `_ner_predictions.jsonl`, `_documents.jsonl`, `_manifest.json`, `_task.json`, e agregado `results/experiment_19b_ner_full_JOBID.md`. Logs e todos os dados individuais ficam em `data/raw/`, ignorado. Não enviar esses ficheiros não desidentificados a GPT/Claude.

Se houver OOM, erro de modelo ou interrupção, guardar logs/outputs e não os sobrescrever nem os declarar completos. Um novo job gera outros nomes. Não há resume: resolver primeiro a causa e voltar a testar. Se esta shell SSH for fechada, recuperar os IDs com `squeue -u "$USER"`/`sacct` e redefinir as variáveis com os IDs efetivos.

## Verificações e sequência restante

Na preparação histórica, 108 testes e bash -n passaram. A correção fc069e15 acrescentou regressões de limites BERT, Unicode, cobertura e fronteiras; os testes correntes estão registados em [THESIS_STATE](THESIS_STATE.md). Nesta revisão documental não houve nova execução NER nem submissão.

Prioridade atual: preservar e verificar o agregado/artefactos do job 15216 e grupos protegidos; preparar posteriormente desidentificação/inspeção e anotação GPT/Claude com labels específicas preservadas e agregação automática. O planeador exige o bundle do mesmo prefixo (manifesto, documentos, menções e previsões no caso NER), fontes originais verificáveis pelos hashes do manifesto e não interpreta checks em falta como negativos. Não criar lotes reais nesta consolidação. Isso não autoriza transmissão nem transforma SILVER em gold. Manter duplicados/processos relacionados no mesmo split futuro e o benchmark de 50 intocado.
