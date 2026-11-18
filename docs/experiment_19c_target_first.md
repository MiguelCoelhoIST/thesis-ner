# 19c — variante experimental target-first

Preparada em 18-11-2026. Não executada com pesos reais nesta revisão.

## Revisão assistida privada

O ficheiro fornecido contém 30 propostas/IDs distintos, todas com `human_validated=false` e revisão pendente. Declara 20 outputs válidos pelo protocolo e 10 inválidos; 6 propostas consideradas plausíveis, 24 sugestões de revisão e 14 outputs válidos estruturalmente sinalizados para revisão semântica. Estas são avaliações assistidas provisórias, não gold, accuracy ou resultados confirmados do replay. Não confundir esta distribuição com os 8/22 declarados para a geração original 15324: a ligação ao artefacto privado de origem não foi verificada neste workspace.

Problemas assinalados, com sobreposição entre categorias: papel de outra pessoa (9 registos), âmbito processual (6), papéis fora da taxonomia (5), evidência de outra pessoa (3), definição de papel (3), contexto insuficiente para o alvo (3), limite de span inválido (1). As sugestões propõem 24 estados supported, 2 ambiguous, 3 insufficient e 1 invalid_entity, incluindo 4 casos multi-label. Não foram aplicadas aos datasets ou inseridas no input do modelo. O ficheiro privado e os seus excertos/identificadores permanecem fora do Git.

## Variante e controlos preservados

[Prompt 19c-v2-target-first](../config/prompts/role_annotation_19c_v2_target_first.txt): 2.740 caracteres/308 palavras, contra 3.280/407 no v1. O número de tokens efetivo será medido pelo preflight, não inferido destas contagens. A entidade literal é apresentada como string JSON antes do mesmo contexto marcado. A ocorrência continua identificada pelos mesmos offsets e marcadores, mesmo se o nome se repetir no texto.

Prioridades: verificar a validade do span, associar cada papel/evidência ao alvo, separar participantes de autores bibliográficos, distinguir processos atuais/citados e abster-se quando necessário. Taxonomia de dez classes, multi-label, other_roles, schema JSON, scopes e estados de abstenção são os mesmos. Não contém demonstrações nem labels/sugestões dos 30 casos.

O [adaptador](../src/annotation/annotate_stj_silver_19c_target_first.py) reutiliza o main, ciclo de inferência e parser existentes, alterando apenas os globais de prompt/build_messages no processo e restaurando-os no fim. Conserva o ficheiro histórico do gerador, v1, loader e revalidador integralmente intactos. Não há novo algoritmo de amostragem, NER ou parser.

O argumento obrigatório `--reference-run` vincula input/manifesto/checkpoint/gerador/loader/taxonomia à execução original v1. Exige 30 registos declarados e confere o hash das previsões históricas, sem as enviar ao modelo. A configuração efetiva deve ser idêntica à referência, exceto prompt_version e prompt_sha256. Mantêm-se seed, FP16, greedy/temperatura 0, thinking desativado, limites de tokens e ausência de truncagem. O validador original volta a conferir o lote protegido e os offsets antes do carregamento.

Cada diretório privado novo guarda o run.json/previsões habituais e `variant.json`, ligando o hash do adaptador, configuração esperada, hash da execução de referência e hash/estado do run atual. O piloto exige o sidecar do seu próprio preflight; não aceita preflight v1, de outro código, lote ou referência. Falha de verificação não pode ser ignorada por um run.json isolado com preflight_passed. Outputs inválidos continuam registados e sujeitos ao contrato de saída original. Nenhuma revisão humana automática, elegibilidade de treino ou conversão em gold.

## Comandos no g09

Atualizar apenas com checkout limpo; usar a seleção original do job 15324, sem a recriar. O caminho pilot03 é o indicado anteriormente pelo utilizador/patch e deve corresponder aos hashes históricos. Não alterar hashes para aceitar outro lote.

```bash
cd ~/thesis-ner
git pull --ff-only origin develop
source venv-ner/bin/activate
PILOT_DIR=data/raw/experiment_19c_pilot03
REFERENCE_RUN=data/raw/experiment_19c_pilot_15324/run.json
export QWEN_REVISION=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["configuration"]["revision"])' "$REFERENCE_RUN")
sinfo -N -o '%N %P %t %G'
scontrol show partition hlt_msc
scontrol show node g06
```

Confirmar autorização/disponibilidade atuais: g06/hlt_msc são os recursos históricos, não verificados nesta sessão. Reutilizar o checkpoint local; não fazer downloads nem executar Qwen no login. Se esses recursos forem apropriados:

```bash
PRE_JOB=$(sbatch --parsable --partition=hlt_msc --nodelist=g06 --gres=gpu:1 \
  scripts/slurm/run_qwen3_19c_target_first.sbatch preflight "$PILOT_DIR" "$REFERENCE_RUN")
PRE_JOB=${PRE_JOB%%;*}
sacct -j "$PRE_JOB" --format=JobID,State,ExitCode,Elapsed
```

Esperar COMPLETED/0:0, conferir `preflight_passed` em run.json **e** o sidecar variant.json em `data/raw/experiment_19c_target_first_preflight_${PRE_JOB}/`, além de GPU, checkpoint e comprimentos. Só depois, sem alterações de código/dados:

```bash
sbatch --partition=hlt_msc --nodelist=g06 --gres=gpu:1 \
  scripts/slurm/run_qwen3_19c_target_first.sbatch pilot "$PILOT_DIR" "$REFERENCE_RUN" \
  "data/raw/experiment_19c_target_first_preflight_${PRE_JOB}/run.json"
```

Os outputs novos ficam em `data/raw/experiment_19c_target_first_pilot_JOBID/`; logs privados têm prefixo stj_19c_target_first. Os wrappers v1 e outputs antigos permanecem disponíveis e não são sobrescritos. As verificações de hash exigem os mesmos bytes do código histórico, incluindo finais de linha.

## Comparação e limitações

Comparar os mesmos IDs e configurações, com o mesmo parser, inicialmente **raw v1 versus raw v2**. Não comparar v1 com evidência recuperada contra v2 sem recuperação como se fossem o mesmo protocolo. O revalidador offline histórico permanece vinculado a v1 e não foi alargado para revalidar esta variante. Conservar separadas conformidade estrutural e avaliação semântica por pessoa, âmbito e papel. Não calcular F1/accuracy sem referência independente.

Esta variante foi informada pela revisão do próprio piloto; o lote é de desenvolvimento exploratório, não teste independente de generalização. Encurtamento e apresentação target-first mudam juntos, portanto uma eventual diferença não isola o efeito de cada fator. Não se demonstrou melhoria do modelo nem se confirmou qualquer sugestão privada como anotação humana. Gold50, corpus, NER e revisões anteriores permanecem preservados.

Validação local: 219 testes, sucesso, 1 integração opcional omitida; 7 testes novos com contextos inventados e GPU/modelo simulados. Incluem preservação das 30 menções/offsets, configurações idênticas fora do prompt, restauração de v1, spans/citações/múltiplas pessoas, mistura de preflights e proteção de inputs. O wrapper Slurm foi verificado sintaticamente; nenhum job foi submetido nesta revisão.
