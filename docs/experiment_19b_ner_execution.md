# Experiência 19b — executar NER integral no g09

Revisto em 11-11-2026. Objetivo imediato: smoke de três textos, depois os 191 textos distintos. Não criar novas amostras por papel nem executar Qwen, treino ou anotação externa nesta etapa.

## Confirmação do caminho de execução

- O preparador relê as 388 fontes, confere hash/comprimento com a auditoria e agrupa por hash do texto extraído. Cada um dos 191 conteúdos tem uma passagem NER, com janelas internas sobrepostas para não cortar nomes; as 388 versões e evidências continuam em `*_documents.jsonl`.
- As janelas cobrem o texto inteiro e não dependem de âncoras. Não há quota de 60/40/430 nem classificação lexical. Mesma pessoa em posições diferentes continua a produzir ocorrências diferentes.
- `*_mentions.jsonl` contém os PER aceites pelos filtros atuais, com contexto, offsets documentais/locais e IDs estáveis por hash/posição. `*_ner_predictions.jsonl` conserva **todas as previsões**, incluindo PER filtradas, outras classes NER e janelas de origem. PER com offsets válidos recebem também contexto e mention_id, mesmo quando filtradas. Não se perde a possibilidade de rever falsos negativos dos filtros. O modelo pode omitir pessoas: cobertura integral não certifica recall perfeito.
- Em `--run-ner`, não se escreve outro `known_mentions_PARTIAL.jsonl`. O smoke é apenas o teste técnico solicitado. Há heartbeat por dez segundos e contagem de documentos/janelas/menções. O manifesto guarda parâmetros, tempos, metadados do modelo e hashes dos inputs/scripts.
- Benchmarks e datasets existentes são apenas lidos. Outputs têm nomes novos por job e recusam sobrescrita. Não há suggested_label nas menções futuras nem labels jurídicas atribuídas pelo NER. Tudo permanece privado em `data/raw/`.

## Taxonomia e anotações futuras

A versão operacional é [role_taxonomy_v2.json](../config/role_taxonomy_v2.json): ARGUIDO, REU, AUTOR, REQUERENTE, RECORRENTE, RECORRIDO, TESTEMUNHA, RELATOR, REFERENCE, UNKNOWN. O ficheiro histórico de nove classes fica intacto para reproduzir experiências anteriores.

O task/schema produzido permite `labels` como lista multi-label, com evidência e âmbito por papel. `other_roles` guarda designação literal, quote e âmbito de papéis fora da lista, sem os transformar automaticamente em novas classes nem perder essa informação. UNKNOWN significa ausência dos nove papéis específicos, não ambiguidade; um papel fora da lista pode ser preservado em other_roles. REFERENCE não implica autorização de preservar identidades.

Guardar sempre as labels finas e a resposta original do anotador. A comparação agrupada deriva depois do mesmo dataset/splits através do mapper existente, usando `--config config/role_taxonomy_v2.json`. REFERENCE mantém uma classe própria na agregação; a configuração pode mudar sem nova anotação fina. Não substituir as labels finas pelo resultado agrupado. Anotações automáticas serão SILVER, nunca human_validated=true.

## Antes de executar: checkout remoto

Os comandos pressupõem que o checkout remoto tem os ficheiros revistos. Não houve transferência automática. Confirmar especialmente:

- `src/data/prepare_stj_corpus_inventory.py` e o detetor existente com `prediction_sink`;
- helpers já usados em `src/annotation/prepare_role_annotation_batch.py` e `src/annotation/export_external_annotation.py`;
- `config/role_taxonomy_v2.json`;
- `scripts/slurm/run_stj_inventory_19b.sbatch`.

Não sincronizar modelos ou dados privados pelo Git. Não sobrescrever alterações remotas sem inspeção. A presença dos ficheiros antigos da 19a é uma pré-condição, não motivo para os voltar a gerar.

## 1. Ligar e verificar Slurm

Executar manualmente, definindo previamente `INESC_USER` com o seu utilizador institucional. Não guardar passwords, tokens ou chaves neste ficheiro:

```bash
ssh g09.hlt.inesc-id.pt -l "$INESC_USER"
cd ~/thesis-ner
mkdir -p data/raw results

sinfo -N -o '%N %P %t %G'
scontrol show node g09
scontrol show partition hlt_msc

test -x venv-ner/bin/python
test -f models/eduardo_extended_model/config.cfg
test -f config/role_taxonomy_v2.json
test -f scripts/slurm/run_stj_inventory_19b.sbatch
test -f data/raw/experiment_19a_audit_v5_gpu_full.json
test -f data/raw/experiment_19a_candidates_v5_gpu_full.jsonl
test -f data/raw/experiment_19a_candidates_v4_smoke10.jsonl
test -f data/eval/roles_eval_real_candidates_v1.jsonl
source venv-ner/bin/activate
python src/data/prepare_stj_corpus_inventory.py --help
bash -n scripts/slurm/run_stj_inventory_19b.sbatch
```

`hlt_msc` é a partição dos scripts históricos, **não uma disponibilidade verificada nesta sessão**. Só avançar com os comandos seguintes se `g09` aparecer nessa partição, com GPUs e autorização aplicável. Se não aparecer, parar e confirmar a partição/NodeName com o administrador; não executar diretamente na GPU nem escolher outro nó automaticamente.

A tentativa SSH desta sessão falhou no DNS; não foi possível verificar ao vivo esses comandos/recursos. Os testes locais validam código e bash, não o scheduler remoto.

## 2. Submeter smoke de três documentos

Ainda na raiz do repositório remoto:

```bash
SMOKE_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist=g09 --gres=gpu:1 scripts/slurm/run_stj_inventory_19b.sbatch smoke)
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

## 3. Submeter o corpus completo depois do smoke

Sem alterar código/inputs entre os jobs:

```bash
FULL_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist=g09 --gres=gpu:1 scripts/slurm/run_stj_inventory_19b.sbatch full "$SMOKE_MANIFEST")
FULL_JOB=${FULL_JOB%%;*}
echo "FULL_JOB=$FULL_JOB"
squeue -j "$FULL_JOB"
tail -f "data/raw/stj_19b_ner_${FULL_JOB}.out"
```

O wrapper full valida o manifesto do smoke (três documentos, menções positivas, mesmo universo, código e hashes dos inputs), depois executa **sem --max-documents**. Não inicia a passagem full se a gate falhar. Não há novo inventário recuperado parcial. O teste de três documentos é repetido dentro da passagem integral para produzir uma saída uniforme; os ficheiros de smoke não são concatenados ao resultado final.

Após terminar:

```bash
sacct -j "$FULL_JOB" --format=JobID,State,ExitCode,Elapsed,MaxRSS
FULL_PREFIX="data/raw/experiment_19b_ner_full_${FULL_JOB}"
python -c 'import json,sys; s=json.load(open(sys.argv[1]))["summary"]; assert s["inventory_complete"] and s["NER_documents_processed"]==191 and s["unique_texts"]==191 and s["audited_documents"]==388; print(json.dumps(s,indent=2))' "${FULL_PREFIX}_manifest.json"
```

Saídas: `${FULL_PREFIX}_mentions.jsonl`, `_ner_predictions.jsonl`, `_documents.jsonl`, `_manifest.json`, `_task.json`, e agregado `results/experiment_19b_ner_full_JOBID.md`. Logs e todos os dados individuais ficam em `data/raw/`, ignorado. Não enviar esses ficheiros não desidentificados a GPT/Claude.

Se houver OOM, erro de modelo ou interrupção, guardar logs/outputs e não os sobrescrever nem os declarar completos. Um novo job gera outros nomes. Não há resume: resolver primeiro a causa e voltar a testar. Se esta shell SSH for fechada, recuperar os IDs com `squeue -u "$USER"`/`sacct` e redefinir as variáveis com os IDs efetivos.

## Verificações e sequência restante

108 testes passaram; bash -n passou localmente. Incluem deduplicação por conteúdo, preservação dos aliases, NER sem âncoras, offsets, previsões inválidas não marcadas como aceites, ausência de novo inventário parcial na inferência e gate de smoke. Não houve execução NER real nem submissão nesta revisão; a situação remota continua por confirmar.

Prioridade até dezembro: concluir NER integral, verificar o agregado e grupos protegidos, preparar desidentificação/inspeção, depois anotação GPT/Claude com labels específicas preservadas e agregação automática. Isso não autoriza transmissão nem transforma SILVER em gold. Mantêm-se os blocos processuais/duplicados no mesmo split futuro e o benchmark de 50 intocado. Sem novas experiências ou arquiteturas fora desta sequência.
