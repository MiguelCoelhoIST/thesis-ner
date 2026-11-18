# Experiência 19c — piloto local Qwen de 30 ocorrências

Estado: implementação e testes sintéticos preparados; **sem amostra real gerada, modelo carregado ou job submetido nesta sessão**. A tentativa SSH não interativa respondeu `Permission denied`; portanto não se confirmou o esquema real no g09, os recursos atuais, os pesos ou versões remotas. Os resultados da 19b continuam os confirmados pelo utilizador (job 15216); este piloto ainda não tem resultados de anotação.

**Atualização posterior:** o utilizador executou a preparação no g09 e comunicou 111 checks, 108 resolvidos, três pendências, 15 grupos bloqueados e zero selecionados/LLM calls. A gate funcionou; não há ainda piloto Qwen concluído. O [diagnóstico privado/público e mecanismo de adjudicação v2](experiment_19c_protection_diagnostic.md) substituem o formato declarativo simples de decisões descrito na primeira versão abaixo. O manifesto privado continua apenas no INESC e não foi lido neste workspace.

O commit preexistente **4b339d3** disponibilizou entretanto o [agregado local do job 15216](../results/experiment_19b_ner_full_15216.md), consultado nesta revisão: confirma os 191/191 textos, 24.467 aceites, 24.977 previsões brutas e **checks gold/piloto `not_requested`**. Confirma também preflight WordPiece dos 191, máximo original 703, máximo seguro 486 e uma subdivisão. Estes agregados não são os registos JSONL nem prova de elegibilidade. As notas históricas de consolidação que diziam relatórios apenas no g09 antecedem esse commit.

## Protocolo e reutilização

O produtor 19b e `load_bound_inventory()` foram inspecionados: cada menção tem ID por hash/offsets, `document_id`, contexto contínuo, offsets locais/documentais, `source_text_sha256`, `context_id`, bloco processual, proveniência e flags de reservas possivelmente null. A preparação valida o **bundle real**, não assume que o contrato observado no código basta: manifesto, documentos, previsões aceites, fontes e hashes, slices e metadados precisam de corresponder. Falhas não são ignoradas. Não executar novamente NER.

[prepare_stj_pilot_19c.py](../src/annotation/prepare_stj_pilot_19c.py) reutiliza a validação do planeador, o leitor documental, normalização, componentes de processos, marking e guards de conteúdo. Seleciona exatamente 30, com seed 42, por hash determinístico e rotação de pistas de descoberta: vocabulário criminal, civil, recurso, testemunho, relatoria, bibliografia, requerimentos, recorrido, placeholders, várias menções e ausência das pistas-alvo. São indicadores de variedade, **não labels gold**. Uma ocorrência por grupo relacionado, sem repetir contexto normalizado ou contextos muito semelhantes. Não há garantia de cobrir todos os papéis ou UNKNOWN/REFERENCE antes da anotação. Menos de 30 grupos elegíveis bloqueia a seleção; não relaxar quotas/proteções silenciosamente.

O gold congelado é verificado pelo hash conhecido e usado apenas para exclusão. O argumento `--pilot-sources` exige o pool v4 de 61, hash `b64857723d32375f8f461fc26fd7c1d3ffd675676980ba0663a2a20dc2200a6e`, para reservar todas as fontes do piloto humano, não usar as suas labels. Não é dependência do NER, mas uma referência obrigatória de proteção nesta nova seleção. Fontes/hash/aliases/processos, contexto contido no documento e similaridade ao candidato produzem exclusões conservadoras. Identidades conflitantes/não resolvidas são excluídas e as reservas propagam-se aos grupos relacionados, inclusive documentos sem menções aceites.

Flags antigas `null/not_requested` permanecem intactas. Só uma **nova verificação explícita** com referências protegidas completas permite a coorte exploratória. Referência protegida sem raiz processual normalizável nem associação documental bloqueia todo o piloto; não é declarada ausente. O relatório anterior referia três IDs gold não normalizáveis; ainda não se verificou se se resolvem no bundle remoto. Se necessário, uma adjudicação **de proveniência**, não anotação de papéis, fica num JSON privado passado a `--protection-decisions`:

```json
{
  "gold:ID_INTERNO_DA_REFERENCIA": {
    "human_confirmed": true,
    "document_ids": ["doc_HASH_VERIFICADO_PRIVADAMENTE"],
    "reason": "Fundamento da verificação local, mantido privado"
  }
}
```

O exemplo acima é o **formato histórico v1 e já não basta**: v2 exige reviewer, fingerprints gerados pelo diagnóstico e evidence local verificada por hash. Uma exclusão exige ainda uma fonte externa com contexto e cabeçalho verificáveis, não apenas `excluded_from_corpus:true`. Usar o [formato atual e comandos](experiment_19c_protection_diagnostic.md). Não preencher automaticamente, inventar uma resolução ou marcar referências como ausentes para fazer passar a gate. Excluir não pode contradizer uma correspondência detetada. Uma preparação bloqueada conserva a auditoria e exige novo diretório para repetir.

Os registos originais não são alterados. A amostra acrescenta apenas `cohort=EXPLORATORY_SILVER_PILOT_NOT_GOLD` e metadados de seleção/verificação, preservando inclusive as flags antigas. Pistas de amostragem ficam apenas na auditoria, nunca no prompt. Não define splits ou elegibilidade de treino.

## Prompt e resposta

O prompt integral usado está em [role_annotation_19c_v1.txt](../config/prompts/role_annotation_19c_v1.txt), versão **19c-v1**, com hash gravado em cada configuração. Zero-shot, sem demonstrações, sem IDs processuais, sugestões lexicais ou labels fornecidas ao modelo. Só instruções fixas e contexto com o alvo marcado por `mark_entity()`.

Taxonomia [v2](../config/role_taxonomy_v2.json): ARGUIDO, REU, AUTOR, REQUERENTE, RECORRENTE, RECORRIDO, TESTEMUNHA, RELATOR, REFERENCE, UNKNOWN. REFERENCE é classe principal; AUTOR é processual civil, REU civil, ARGUIDO criminal. Condenação não estabelece automaticamente ARGUIDO atual; autoria de obra não estabelece AUTOR. Papéis citados ficam assinalados por atribuição e não são transferidos para o processo atual.

Resposta JSON estrita: `status`, `assignments`, `other_roles`, `uncertain`, `uncertainty_reason`. Cada atribuição tem label, tipo de evidência, quote literal contínua <=240 caracteres e âmbito. Outros papéis conservam designação literal, evidência e âmbito, sem criar novas classes principais. UNKNOWN é exclusivo entre labels principais e não substitui insuficiência, ambiguidade ou entidade inválida. Um papel só fora da taxonomia pode coexistir com UNKNOWN em `other_roles`. Invalid JSON, chaves duplicadas, labels inválidas, quotes ausentes, incoerências e limite de geração ficam registados; sem reparar JSON ou mapear erros para UNKNOWN.

[annotate_stj_silver_19c.py](../src/annotation/annotate_stj_silver_19c.py) reutiliza o loader offline extraído do protótipo 19b e o chat template/device da Experiência 17. O modo histórico de 40 permanece suspenso e com o seu protocolo. A 19c não usa `suggested_label` nem o validador dos 40. O wrapper novo é [run_qwen3_19c_pilot.sbatch](../scripts/slurm/run_qwen3_19c_pilot.sbatch).

Configuração fixa: Qwen/Qwen3-8B, revision imutável de 40 hexadecimais já em cache, **FP16 explícito**, batch 1, seed 42, `do_sample=False`, temperatura 0, `enable_thinking=False`, 1024 tokens novos, no máximo 4096 tokens de entrada e limite de posições do modelo respeitado, sem truncagem. FP16 é explícito para não presumir BF16 nativo na Quadro RTX 6000 histórica. Versões/hardware podem afetar determinismo; isto não promete equivalência bit a bit com a Experiência 17.

Preflight GPU carrega os pesos locais, aplica o chat template e valida o orçamento de **todos os 30**; não gera labels. O job piloto exige o seu `run.json`, com dados/prompt/código/checkpoint/configuração iguais, e confere versões/template novamente. Inferência gera e grava um registo de cada vez. Todos os outputs são SILVER, com original/raw/estrutura/erros/configuração e `human_validated=false`. Outputs inválidos são conservados nos 30 e produzem `completed_with_invalid_outputs`/exit 1; uma falha de runtime conserva o parcial, não finge conclusão. Não há resume/sobrescrita: usar novos diretórios/jobs.

## Comandos no INESC

Executar manualmente em SSH autorizado, definindo `INESC_USER` localmente; não incluir passwords em comandos/scripts:

```bash
ssh g09.hlt.inesc-id.pt -l "$INESC_USER"
cd ~/thesis-ner
git status --short
# Só fazer pull se o checkout remoto estiver limpo; não sobrescrever alterações.
git switch develop
git pull --ff-only origin develop
source venv-ner/bin/activate
mkdir -p data/raw
sinfo -N -o '%N %P %t %G'
scontrol show partition hlt_msc
scontrol show node g06
python -m pip show torch transformers accelerate
bash -n scripts/slurm/run_qwen3_19c_pilot.sbatch
```

Confirmar disponibilidade/permissão atual antes de submeter; g06/hlt_msc são os recursos históricos, não verificados agora. Verificar cache **sem downloads, carregamento do modelo ou inferência no login**:

```bash
python - <<'PY'
import json
from pathlib import Path
from huggingface_hub.constants import HF_HUB_CACHE
folder = Path(HF_HUB_CACHE) / 'models--Qwen--Qwen3-8B' / 'snapshots'
for snapshot in sorted(folder.iterdir()) if folder.is_dir() else []:
    index = snapshot / 'model.safetensors.index.json'
    shards = set(json.loads(index.read_text())['weight_map'].values()) if index.is_file() else {'model.safetensors'}
    print(snapshot.name, 'weights_complete=', all((snapshot / s).is_file() and (snapshot / s).stat().st_size > 0 for s in shards),
          'tokenizer_config=', (snapshot / 'tokenizer_config.json').is_file())
PY
```

Ausência de snapshot completo bloqueia a execução; não instalar/descarregar por iniciativa deste script. Selecionar manualmente a revision verificada: `export QWEN_REVISION=HASH_DE_40_HEXADECIMAIS`. Inventário de shards não substitui o preflight de carregamento.

Confirmar bundle/fonte e referência privada do piloto, sem imprimir conteúdos:

```bash
for suffix in mentions.jsonl manifest.json documents.jsonl ner_predictions.jsonl; do
  test -f "data/raw/experiment_19b_ner_full_15216_${suffix}" || exit 1
done
test -f data/raw/experiment_19a_candidates_v4_smoke10.jsonl
sha256sum data/raw/experiment_19a_candidates_v4_smoke10.jsonl
```

Se faltar o pool privado de proteção, transferi-lo apenas pelo procedimento institucional autorizado para `data/raw/` no INESC; não o obter pelo Git nem omitir a proteção. O comando seguinte não carrega Qwen nem NER e pode preparar a amostra no login, sujeito às políticas locais:

```bash
python -u src/annotation/prepare_stj_pilot_19c.py \
  --input data/raw/experiment_19b_ner_full_15216_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_ner_full_15216_manifest.json \
  --gold data/eval/roles_eval_real_candidates_v1.jsonl \
  --pilot-sources data/raw/experiment_19a_candidates_v4_smoke10.jsonl \
  --output-dir data/raw/experiment_19c_pilot01 --seed 42
```

Só continuar com `selection_complete=true`, 30 IDs/grupos distintos e zero referências não resolvidas. Inspecionar privadamente `selection_manifest.json`; não mostrar nomes ou contextos em relatórios públicos. Se houver bloqueio, rever a auditoria/resoluções e repetir para `pilot02` com `--protection-decisions` quando aplicável. Não relaxar os filtros para obter 30. Definir `PILOT_DIR` para o diretório efetivamente aprovado:

```bash
PILOT_DIR=data/raw/experiment_19c_pilot01
PRE_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist=g06 --gres=gpu:1 \
  scripts/slurm/run_qwen3_19c_pilot.sbatch preflight "$PILOT_DIR")
PRE_JOB=${PRE_JOB%%;*}
sacct -j "$PRE_JOB" --format=JobID,State,ExitCode,Elapsed
```

**Esperar e inspecionar** COMPLETED/0:0 e `status=preflight_passed` em `data/raw/experiment_19c_preflight_${PRE_JOB}/run.json`. Verificar modelo/revision, template, 30 contagens de tokens, GPU/distribuição de dispositivos, memória/tempos e configuração. Não submeter se houver falhas, alterações de dados/código ou recursos não autorizados. Depois:

```bash
sbatch --partition=hlt_msc --nodelist=g06 --gres=gpu:1 \
  scripts/slurm/run_qwen3_19c_pilot.sbatch pilot "$PILOT_DIR" \
  "data/raw/experiment_19c_preflight_${PRE_JOB}/run.json"
```

Cada job pede 1 GPU por CLI, 4 CPUs, 32 GB de RAM e até 2 horas; verificar limites do INESC. Nunca fixar GPU física nem executar Qwen diretamente no login. A inspeção/submissão manual é necessária nesta sessão sem autenticação SSH do agente.

Saídas privadas por job: `data/raw/experiment_19c_pilot_JOBID/silver_predictions.jsonl`, `run.json`, `aggregate.json`; logs `data/raw/stj_19c_JOBID.{out,err}`. A amostra e `selection_manifest.json` também são privados. Não publicar `other_roles`, quotes, raw outputs, identidades ou mapas. Apenas agregados poderão ser revistos posteriormente para `results/`; não foi criado um resultado fictício nesta implementação.

## Limitações e validação

### Recuperação offline de evidência de gerações guardadas

O patch fornecido pelo utilizador declara que o piloto 15324 produziu 30 propostas, com 8 estruturalmente válidas e 22 inválidas. [Agregado declarado e diagnóstico](../results/experiment_19c_pilot_15324_aggregate.md). Os logs privados não foram consultados neste workspace. A recuperação implementada é uma etapa explícita posterior à geração. Preserva o parser e prompt 19c-v1 e a configuração histórica para permitir comparação com a saída original.

[revalidate_stj_silver_19c.py](../src/annotation/revalidate_stj_silver_19c.py) usa exclusivamente as respostas guardadas. Remove marcadores na comparação e permite variação de whitespace para localizar um único excerto. A evidência derivada contém os caracteres exatos do contexto, com offsets da correspondência e limite de 240 caracteres. Correspondências ambíguas, paráfrases e diferenças de pontuação, letras ou acentos mantêm a rejeição. Evidências já válidas são conservadas. Repetições, âmbito, UNKNOWN, labels e token-limit continuam sujeitos às regras originais.

O comando revalida o bundle protegido, os 30 IDs/ordem/metadados, prompt/taxonomia/parser, loader e hashes dos artefactos históricos. Rejeita chaves JSON duplicadas e números não finitos nos ficheiros históricos. Escreve uma cópia privada com raw e configuração originais, run histórico completo (ambiente, job, duração e contagens de tokens quando existentes), metadados adicionais por proposta, fingerprint da proposta original, entrada derivada do parser, auditoria de recuperações, novo hash de previsões e resumos antes/depois. `LLM_calls=0`, revisão humana pendente e elegibilidade de treino `NOT_ESTABLISHED` obrigatória. A conclusão da revalidação tem exit 0 mesmo com propostas ainda inválidas, comunicadas por `revalidated_with_invalid_outputs` e pelas contagens. A geração GPU mantém o seu contrato histórico de exit 1 para outputs inválidos.

Depois de aplicar a implementação no mesmo checkout do INESC, executar em CPU a partir da raiz com `venv-ner` ativo e um diretório de saída novo.

```bash
python -u src/annotation/revalidate_stj_silver_19c.py \
  --input data/raw/experiment_19c_pilot03/pilot_input.jsonl \
  --selection-manifest data/raw/experiment_19c_pilot03/selection_manifest.json \
  --source-run-dir data/raw/experiment_19c_pilot_15324 \
  --output-dir data/raw/experiment_19c_revalidated_15324_v1
```

A validade estrutural recuperada exige revisão semântica da atribuição à menção alvo. A contagem de evidências recuperáveis difere da contagem de registos recuperados, pois um registo pode ter vários excertos e outros erros. A execução real deste replay está pendente. Os testes sintéticos verificam recuperação literal, ambiguidade, preservação de erros e fontes, ausência de carregamento Qwen, hashes e bundle protegido.

O caminho `pilot03` acima é o indicado no patch, não foi inspecionado remotamente. Usar o input/manifesto originais do job 15324: se forem outros, indicar esses caminhos. Não editar os hashes para aceitar um lote diferente. `historical_binding_mismatch` exige conferir os artefactos/código byte a byte originais (incluindo finais de linha), nunca contornar a verificação. A proposta derivada continua SILVER, sem revisão semântica automática, mesmo quando recupera conformidade estrutural.

Validação local desta revisão: **212 testes**, sucesso, **1 integração opcional omitida**; **35 no módulo do piloto**. Os testes usam apenas dados inventados, cobrem correspondências únicas/sobrepostas, metadados/raw/offsets, loader e integridade do bundle, duplicação JSON/IDs, alterações durante o replay e saída CLI sem conteúdo privado. Não foi executada recuperação sobre dados reais nem nova chamada LLM.

Os testes usam apenas corpus e respostas inventados, incluindo uma execução simulada preflight→30 previsões; não validam GPU/modelo/cache real. A amostra é exploratória e enviesada por critérios de variedade/proveniência, não representativa nem gold; não calcular accuracy/F1 sem referência independente. Literalidade da evidência não prova atribuição jurídica correta. NER pode omitir pessoas, confundir entidades e omitir autores citados. Similaridade e normalização de processos não certificam independência absoluta nem ausência de exposição no pré-treino. Anotações Qwen não são gold independente para avaliar o próprio Qwen.

Suite local: **152 testes**, sucesso, **1 integração opcional omitida**; **18 específicos da 19c**. Loader e geração testados com mocks, não com pesos reais. Scripts usam `umask 077` para novos outputs privados no Linux e recusam sobrescrita; isto não anonimiza os dados nem substitui políticas institucionais de acesso/retenção.

Sem APIs externas, chamadas pagas, treino, downloads, NER repetido ou alterações no corpus, benchmarks, revisões ou `silver.spacy`. A execução massiva continua fora do âmbito. Depois do piloto real, rever parsing, abstenções, múltiplos papéis, REFERENCE/UNKNOWN, âmbito e exemplos difíceis antes de decidir qualquer ampliação.
