# Experiência 19b — propostas SILVER com Qwen3-8B

**Estado em 16-11-2026: protótipo histórico SUSPENSO, NÃO pronto para a Experiência 19c.** Preserva-se o trabalho, sem execução ou adaptação para anotador final. A prioridade atual é preparar anotação assistida GPT/Claude, separada das futuras experiências de classificação Qwen. Ver [estado atual](THESIS_STATE.md) e [decisões](DECISIONS.md).

Atualização posterior: o utilizador autorizou um [piloto 19c separado de 30](experiment_19c_qwen_pilot.md). Apenas o loader offline foi extraído para reutilização; o modo histórico de 40 e o seu prompt continuam suspensos. A prioridade GPT/Claude acima é histórica e foi precedida por este novo piloto local, sem autorização para execução massiva ou APIs.

Limitações do contrato preservado: exatamente 40 candidatos; `suggested_label` necessário para comparação agregada (nunca enviado ao modelo); taxonomia histórica de nove labels com REFERENCE em campo separado; sem suporte completo a `other_roles` nem resume. A configuração v2 atual inclui REFERENCE como classe principal. Os comandos abaixo são históricos e não constituem autorização de execução. As falhas CUDA/DNS descritas pertencem à tentativa local antiga, não ao NER integral concluído no INESC.

## Orientação posterior do utilizador: separar anotação e avaliação

1. **Anotação assistida por GPT/Claude**, inspirada no procedimento referido pelo utilizador como usado pelo professor Borbinha. Esse procedimento ainda não foi fornecido/inspecionado: não assumir modelo, prompt, interface, garantias de privacidade ou validação. Escolha de ferramenta e transferência de textos privados exigem decisão explícita antes de qualquer envio. As propostas continuam SILVER até validação independente apropriada.
2. **Qwen local para experiências de classificação.** A implementação abaixo fica preparada, não escolhida como estratégia definitiva de anotação. Não instalar/descarregar pesos nem gastar recursos de inferência antes dessa decisão. Não usar propostas do próprio Qwen como gold independente da sua avaliação.

O utilizador confirmou acesso histórico ao INESC, repositório `~/thesis-ner`, ambiente `venv-ner` com CUDA e utilização anterior da GPU física 3 na Experiência 19a. Isso não autoriza executar fora de Slurm nem comprova disponibilidade atual. A verificação SSH desta sessão falhou na resolução de `g09.hlt.inesc-id.pt`; `Resolve-DnsName` também falhou. Não se verificaram remotamente Slurm, dependências, GPUs ou cache, e não se submeteu nenhum job. Confirmar a ligação/rede/DNS institucional necessária, sem inferir que o endereço fornecido está incorreto.

## Estado em 30-10-2026

Implementação e testes sintéticos concluídos; **inferência real ainda bloqueada**. A tentativa de smoke test selecionou deterministicamente cinco dos 40 candidatos, mas terminou com `cuda_unavailable` antes de carregar o modelo. Foram geradas zero respostas e não foi criado um dataset SILVER fictício/vazio.

Ambiente observado: PyTorch `2.11.0+cpu`, Transformers `4.53.2`, CUDA indisponível. A cache contém um snapshot de metadados/tokenizer do Qwen3-8B, mas **zero ficheiros de pesos**. Não foram instaladas dependências nem descarregados modelos. A presença de hardware NVIDIA ou dos scripts antigos não comprova um ambiente PyTorch CUDA utilizável. Não foi confirmado acesso/sessão INESC autorizado nesta execução; não houve SSH, submissão de jobs ou transferência de dados.

Resultado agregado da tentativa: [experiment_19b_smoke01_aggregate.md](../results/experiment_19b_smoke01_aggregate.md). Metadados privados: `data/raw/experiment_19b_smoke01_run.json`. A ausência de outputs inválidos com zero gerações não é sucesso de parsing/inferência.

## Método e representação

Entrada: `data/raw/experiment_19a_annotation_batch01_v1.jsonl`, os 40 candidatos originais selecionados na Experiência 19a. O script exige esse tamanho e candidatos ainda não anotados, valida o JSONL e a ocorrência exata por offsets. Não consulta o gold50, revisões humanas ou treino. Não há demonstrações few-shot.

Executável: [annotate_role_candidates_qwen.py](../src/annotation/annotate_role_candidates_qwen.py).

Reutiliza a Experiência 17 para as classes do modelo/tokenizer, `render_prompt()` (chat template com `enable_thinking=False`), `model_input_device()` e `device_information()`. A inicialização, antes embutida no `main()` da Experiência 17, é adaptada sem alterar aquele script: mesmo Qwen/Qwen3-8B, dtype automático, device map automático em CUDA, `eval()` e inferência sem gradientes. Usa a função canónica `mark_entity()`.

O novo prompt é **`19b-zero-shot-json-v1`**, não o prompt de cinco classes da Experiência 17. As mensagens recebem apenas instruções fixas e texto marcado: **nenhum `suggested_label`, ID ou metadado processual é enviado ao modelo**. O campo lexical só é utilizado posteriormente para agregados de comparação.

Configuração: seed 42, batch size 1, greedy decoding (`do_sample=False`), temperatura 0, thinking desativado, até 1024 novos tokens. O orçamento de 16 tokens da Experiência 17 não permite JSON com evidência e, por isso, não é reutilizado. Não há truncagem silenciosa da entrada; excesso de contexto é registado como erro. Seed e greedy não garantem equivalência bit a bit entre versões/hardware.

Todo o carregamento é **offline/local** (`local_files_only=True`, Hub/Transformers offline, telemetry desativada). A máquina autorizada precisa dos pesos completos já em cache. Não existe API de inferência, fallback para outro modelo, reparação automática de JSON ou conversão de erros para UNKNOWN.

### Labels e categoria experimental

Os nove papéis finos mantêm a configuração atual: ARGUIDO, REU, AUTOR, REQUERENTE, RECORRENTE, RECORRIDO, TESTEMUNHA, RELATOR, UNKNOWN. Cada atribuição inclui label, evidência, excerto literal curto e âmbito.

`REFERENCE` é **uma categoria experimental separada**, autorizada para esta experiência, para autoria bibliográfica de obras/artigos citados. Vai em `experimental_categories`, não em `proposed_labels` da taxonomia fina. Não foi acrescentada ao mapper/configuração, não substitui uma taxonomia final CITATION_AUTHOR e não autoriza preservar nomes. Não confundir com AUTOR processual, mera citação de outro acórdão ou UNKNOWN.

O status pode ser `supported`, `ambiguous`, `insufficient` ou `invalid_entity`. Ambiguidade exige justificação; insuficiência/entidade inválida exigem lista vazia, não UNKNOWN forçado. UNKNOWN é exclusivo e significa pessoa válida sem papel-alvo suportado, com evidência/âmbito `not_applicable`. REFERENCE também não coexiste com UNKNOWN, mas pode coexistir com outro papel suportado.

Para papéis positivos, evidência `explicit` ou `inferred` exige uma quote contínua exata do texto original, de até 240 caracteres. O parser verifica a existência literal, **não a correção jurídica da relação**. Âmbito por label: `current_proceeding`, `cited_proceeding`, `both` ou `uncertain`; REFERENCE/UNKNOWN usam `not_applicable`. O prompt proíbe concluir automaticamente ARGUIDO atual a partir de condenação e AUTOR processual a partir de autoria textual.

### Outputs privados e controlo

Cada saída mantém o registo original e os seus campos de proveniência. Acrescenta `annotation_tier="SILVER"`, `annotation_source="llm"`, `proposed_labels`, `experimental_categories`, resposta estruturada/raw, status, erros de parsing e configuração. `label` permanece null; **`human_validated` é sempre false** e `requires_review` é true. Evidência/dificuldade originais não são preenchidas como se fossem humanas.

O script grava incrementalmente cada resultado privado; não sobrescreve saídas anteriores e não implementa resume. Em interrupção, conservar o parcial e metadados e escolher novos nomes para repetir. Não concatenar parciais sem verificar IDs/configuração. Raw output e quotes nunca entram no relatório público.

O manifesto de execução regista hashes do input/script/prompt, prompt fixo, seed, IDs/ordem, revision pedida e commit resolvido do modelo, commit do tokenizer quando disponível, hash do chat template, bibliotecas, device, tempos e erros. Usar uma revision imutável para repetição. O smoke test de cinco casos é obrigatório antes dos restantes 35 na mesma execução/configuração; se os cinco produzirem erro de schema, a execução dos restantes não começa. `ambiguous`/`insufficient` são respostas estruturalmente válidas, não erro de parsing.

O relatório automático em `results/` contém apenas distribuições, multi-label, evidência/âmbito, ambiguidades/abstenções, erros e comparação lexical. A distribuição inclui propostas tentativas válidas, mas existe contagem separada de labels com status `supported`. Concordância com âncoras **não é accuracy**; não se calcula precisão/recall/F1 sem gold independente. O denominador da comparação exclui outputs inválidos e casos sem proposta fina, apresentados separadamente.

## Executar no INESC

Os comandos seguintes são para uma shell Linux **já autorizada no INESC**, na raiz do checkout. Não foram executados nesta sessão. Não supõem um hostname SSH nem fazem upload. Os inputs privados não viajam pelo Git: confirmar a sua presença através do procedimento institucional autorizado.

Pré-condições: ambiente `venv-ner` com PyTorch CUDA/Transformers/Accelerate, snapshot completo do Qwen3-8B local, permissão para processar estes textos e recursos Slurm confirmados. O [template novo](../scripts/slurm/run_qwen3_19b.sbatch) reutiliza `hlt_msc`, GPU `RTX_6000_24GB`, 32 GB RAM e 2 horas dos scripts anteriores, sem fixar nó; **disponibilidade/permissão atuais não foram verificadas**. O template exige `SLURM_JOB_ID`, ativa `venv-ner` e não altera `CUDA_VISIBLE_DEVICES`. Logs Slurm ficam em `data/raw/`, não em `results/`.

### Verificações apenas de leitura, antes de decidir qualquer submissão

Depois de estabelecer a ligação SSH autorizada, executar no INESC:

```bash
cd ~/thesis-ner
command -v sbatch sinfo scontrol squeue
sinfo -N -o '%N %P %t %G'
scontrol show partition
squeue -u "$USER" -o '%.18i %.9P %.2t %.10M %.6D %R'
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv

source venv-ner/bin/activate
python - <<'PY'
import importlib.metadata as metadata
import json
from pathlib import Path
for package in ('torch', 'transformers', 'accelerate', 'huggingface-hub'):
    try:
        print(package, metadata.version(package))
    except metadata.PackageNotFoundError:
        print(package, 'NOT_INSTALLED')
try:
    import torch
    print('torch_compiled_cuda', torch.version.cuda)  # no model/GPU inference
except ImportError:
    print('torch_import_failed')
try:
    from huggingface_hub.constants import HF_HUB_CACHE
    folder = Path(HF_HUB_CACHE) / 'models--Qwen--Qwen3-8B' / 'snapshots'
    snapshots = sorted(folder.iterdir()) if folder.is_dir() else []
    print('qwen_cached_snapshots', len(snapshots))
    for snapshot in snapshots:
        index = snapshot / 'model.safetensors.index.json'
        if index.is_file():
            shards = set(json.loads(index.read_text())['weight_map'].values())
        else:
            shards = {'model.safetensors'}
        present = sum((snapshot / name).is_file() and (snapshot / name).stat().st_size > 0 for name in shards)
        print('revision', snapshot.name, 'expected_shards', len(shards),
              'present_shards', present, 'complete_inventory', present == len(shards))
except ImportError:
    print('cache_inspection_unavailable_without_huggingface_hub')
PY
```

Estes comandos não instalam bibliotecas, descarregam pesos, leem acórdãos ou executam inferência. Inventário de shards completo não certifica integridade/compatibilidade do modelo. Não concluir que uma GPU sem utilização está autorizada/disponível: confrontar estado Slurm, partição e políticas locais. Não fixar `CUDA_VISIBLE_DEVICES=3` no job; o scheduler deve atribuir as GPUs e respetiva numeração lógica.

### Comandos de execução futura — NÃO autorizados para submissão nesta fase

Só depois de decidir a estratégia e obter confirmação para gastar recursos, executar os comandos seguintes. Uma falha de dependência/cache é motivo para reportar e pedir direção, não instalar ou descarregar automaticamente.

```bash
source venv-ner/bin/activate
mkdir -p data/raw
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
python -c 'import torch; print(torch.__version__, torch.cuda.is_available())'
python src/evaluation/validate_role_candidates_v2.py data/raw/experiment_19a_annotation_batch01_v1.jsonl

# Identificar a revision dos metadados em cache; confirmar também os pesos completos.
export QWEN_REVISION="$(python -c "from transformers import AutoConfig; print(AutoConfig.from_pretrained('Qwen/Qwen3-8B', local_files_only=True)._commit_hash)")"
test "${#QWEN_REVISION}" -eq 40
sbatch scripts/slurm/run_qwen3_19b.sbatch smoke
```

Após o job smoke terminar com `smoke_passed` e cinco outputs válidos, consultar apenas o agregado em `results/experiment_19b_smoke_JOBID_aggregate.md`. Rever os erros privados se falhar; não promover sucesso de parsing a correção jurídica. Depois:

```bash
sbatch scripts/slurm/run_qwen3_19b.sbatch full
```

O job full produz `data/raw/experiment_19b_full_JOBID_silver.jsonl`, metadados `..._run.json` e relatório `results/experiment_19b_full_JOBID_aggregate.md`. Reexecuta internamente os cinco primeiros para a gate, inclui-os uma única vez nos 40 e não junta o smoke separado ao dataset final.

Alternativa direta, dentro de uma alocação GPU autorizada, com nomes novos:

```bash
python -u src/annotation/annotate_role_candidates_qwen.py \
  --input data/raw/experiment_19a_annotation_batch01_v1.jsonl \
  --output data/raw/experiment_19b_full01_silver.jsonl \
  --run-metadata data/raw/experiment_19b_full01_run.json \
  --report results/experiment_19b_full01_aggregate.md \
  --revision "$QWEN_REVISION" --device cuda --seed 42
```

Para executar só cinco nessa alocação, acrescentar `--smoke-only` e usar nomes novos para os três outputs. Não executar o comando CPU por engano num login node nem descarregar pesos automaticamente ao encontrar cache incompleta.

## Testes e limitações científicas

81 testes passaram localmente, incluindo nove novos de esquema/parsing estrito, quotes, offsets, ocultação da sugestão, multi-label, REFERENCE, UNKNOWN, abstenção e ausência de validação humana. Testes sintéticos não substituem o smoke real de carregamento/chat template/geração, que permanece pendente.

SILVER não é parecer jurídico nem gold. A comparação com sugestões lexicais pode partilhar vieses de descoberta. Nem evidência citada literalmente nem consistência do JSON comprovam atribuição correta. Recomenda-se adjudicação jurídica dirigida a ambiguidades, divergências, REU, referências e uma amostra de propostas aparentemente claras, sem exigir anotação manual de todos os 40 ao utilizador. Os três casos só com cabeçalho mantêm a pendência de proveniência da Experiência 19a; o LLM não resolve identidade documental.

Não há resultados desta experiência que permitam calcular desempenho. O gold50 e as dez revisões piloto permanecem separados e intocados. A coleção SILVER não deve ser usada como gold independente para avaliar o próprio Qwen que a produziu, e não foi autorizado treino. UNKNOWN continua dependente do viés de descoberta deste lote; futuros negativos reais exigem amostragem independente e não labels automáticas.
