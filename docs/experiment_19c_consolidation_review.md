# Revisão local antes da Experiência 19c

**Atualização da consolidação autorizada — 16-11-2026:** os blocos de análise/proposta abaixo preservam o snapshot da primeira revisão, que não autorizava commits. O utilizador autorizou posteriormente correções, quatro commits e push após validação. Implementação e verificação concluídas nesta consolidação; não iniciou a Experiência 19c nem executou os protótipos sobre dados reais.

- Planeador: checks ausentes/indeterminados ficam em revisão; reservas/motivos propagam-se por hashes, documentos, blocos, processos e aliases, incluindo documentos sem menções selecionadas. Recusa labels escalares/múltiplas e propostas SILVER pré-preenchidas. Cada lote conserva IDs, grupos originais, grupos de planeamento e motivos; não há splits nem elegibilidade de treino atribuídos.
- Associação de inputs: valida manifesto e ficheiros companheiros do mesmo prefixo, IDs de documento/menção/contexto derivados de hash/offsets, metadados e conjunto exato de previsões PER aceites; relê fontes canónicas com o leitor existente, confere fingerprints do manifesto, hash do texto e fatias de contexto. Grava fingerprints do bundle e fontes no novo plano privado; não executa NER. Fontes movidas/ausentes e bundles antigos sem fingerprints suficientes falham explicitamente, inclusive com `--allow-partial`. A consistência não equivale a autenticar um bundle integralmente falsificado.
- Qwen: código, wrapper, testes e guia identificados como protótipo histórico suspenso, incompatível com o protocolo 19c. Nenhuma execução ou adaptação de taxonomia.
- Relatórios: sete agregados preservados com notas históricas, sem alterar números. Guia NER corrigido quanto a referências opcionais, nó Slurm e guard WordPiece; guia do exportador distingue cinco/40 e corpus completo.
- Estado confirmado pelo utilizador: job **15216, COMPLETED, ExitCode 0:0**, 388 documentos auditados, 191 textos processados, 24.467 ocorrências PER aceites, 24.977 previsões brutas, `inventory_complete=True`, `NER_executed=True`, `LLM_calls=0`; correção Transformer **fc069e15**. Relatórios remotos não foram consultados. Não são labels jurídicas anotadas.
- Validação corrente: **134 testes, sucesso, uma integração opcional omitida**; planeador **18/18**, Qwen **9/9**. Testes são sintéticos, sem modelos, NER, APIs, treino ou dados reais. Checks finais de isolamento, links, privacidade e hashes dos inputs protegidos precedem o push. `data/raw/silver.spacy` está incluído na verificação de preservação.

Os quatro grupos aprovados mantêm as mensagens da proposta abaixo: planeador/testes; protótipo Qwen; sete relatórios; documentação consolidada. Para hashes e ficheiros efetivamente incluídos, consultar o histórico Git. Não há autorização de transmissão ou início da 19c nesta consolidação.

Data: 16-11-2026. Revisão de código, testes e documentação; sem treino, inferência, envio externo, submissões Slurm, commit ou push. Nenhum dataset foi alterado. Esta é uma proposta de consolidação, não um relatório de execução remota.

## Git e limites da evidência

Depois de `git fetch origin`, a branch é `develop`, HEAD `fc069e15bac5d1638848efa3e2d782de23b86f56`, com **0 commits à frente e 0 atrás** de `origin/develop`. Havia 16 ficheiros pendentes: dois modificados e 14 não rastreados. Nenhuma alteração foi sobrescrita ou staged.

O utilizador confirmou o job 15216: **388 documentos, 191 textos distintos, 191/191 processados, 24.467 PER aceites, 24.977 previsões PER brutas**, `inventory_complete=True`, `NER_executed=True`, `LLM_calls=0`. Os relatórios dos jobs 15209, 15215 e 15216 estão apenas no g09 e não foram consultados. Não criar substitutos locais como se tivessem sido inspecionados. Não inferir tempos, versões, grupos protegidos ou distribuição de papéis.

## Classificação dos ficheiros pendentes

Todos os caminhos abaixo são relativos à raiz. Manter os relatórios históricos não significa adotar as suas instruções como protocolo atual.

| Ficheiro | Recomendação |
| --- | --- |
| `docs/THESIS_STATE.md` | Manter; atualizado nesta revisão com o resultado confirmado, fonte/limites, taxonomia v2 e prioridades 19c. Backlogs anteriores identificados como históricos. |
| `docs/DECISIONS.md` | Manter; atualizadas contradições de taxonomia/estado e acrescentadas D21–D23. Não inventar o procedimento do professor. |
| `docs/experiment_19b_silver_annotation.md` | Manter como documentação do protótipo Qwen suspenso; antes de versionar, explicitar no topo que a execução histórica de 40 e REFERENCE separada não são o protocolo 19c. A falha DNS/CUDA descrita é histórica/local, não o estado atual do NER remoto. |
| `docs/external_annotation_export.md` | Manter como documentação do exportador histórico 5/40. Corrigir a contradição entre “40 por omissão” e “opera apenas nos cinco contextos”; qualificar as suites 89/92 como verificações históricas. Não apresentar a CLI de candidatos como exportador pronto para o inventário completo. |
| `results/experiment_19a_v5_gpu_full_annotation_audit.md` | Manter como auditoria agregada histórica do pool de 430, não do inventário completo. |
| `results/experiment_19a_annotation_batch01_v1_report.md` | Manter como snapshot da seleção de 40 e exclusões. Quotas humanas, nove classes e CITATION_AUTHOR refletem aquela fase; ligar ao estado atual em vez de alterar contagens históricas. |
| `results/experiment_19b_smoke01_aggregate.md` | Manter como evidência do smoke Qwen local bloqueado, com zero gerações; não confundir com smoke NER Slurm nem sucesso de anotação. |
| `results/experiment_19b_external_pilot01_export_validation.md` | Manter: validação técnica histórica de cinco exports, sem envio nem anonimização certificada. |
| `results/experiment_19b_external_full01_export_validation.md` | Manter: validação técnica histórica dos 40; “full01” não significa corpus completo. Não fundir com o relatório do piloto nem apagar o alerta registado. |
| `results/experiment_19b_corpus_plan02.md` | Manter como planeamento com 384 ocorrências e extrapolação condicional, acrescentando enquadramento histórico antes de versionar. Não usar ~27 mil como medição atual. |
| `results/experiment_19b_corpus_inventory_20261111.md` | Manter como recuperação parcial de 412, com enquadramento histórico. A contagem atual é a confirmação do job 15216; comandos que pedem novo NER são anteriores à conclusão. |
| `src/annotation/plan_inventory_batches.py` | Manter e reutilizar, mas corrigir os checks de reservas/anotação e testar a CLI antes de o usar para elegibilidade 19c. Não executar sobre dados reais nesta revisão. |
| `tests/test_inventory_batches.py` | Manter; três testes passam. Falta cobertura dos checks não realizados, listas `labels` preenchidas e vinculação input/manifesto. |
| `src/annotation/annotate_role_candidates_qwen.py` | Manter como protótipo histórico suspenso. Não adaptar nem executar nesta fase; não é o anotador GPT/Claude nem o protocolo v2 integral. |
| `tests/test_qwen_silver_annotation.py` | Manter; nove testes passam e documentam o contrato histórico. Não interpretar como teste de inferência nem atualizá-los isoladamente para v2 sem mudar o protocolo correspondente. |
| `scripts/slurm/run_qwen3_19b.sbatch` | Manter apenas como wrapper histórico suspenso, com essa indicação explícita antes de versionar. Continua preso ao lote de 40; não submeter como job 19c. |

Este relatório é um novo ficheiro de documentação criado na consolidação, além dos 16 inicialmente pendentes. Não foram modificados scripts, testes, resultados históricos ou configurações.

## Problemas concretos e correções propostas

### Planeador de lotes: útil, mas ainda não uma barreira contra leakage

Pontos positivos: não há quota por papel; inclui todos os IDs; ordenação determinística; verifica offsets e duplicados; separa coortes conhecidas; não exporta textos nem chama NER/LLM; exige outputs novos em diretório privado ignorado e recusa inventários parciais por omissão. As coortes não são splits e a presença de um processo em vários lotes não é, por si só, leakage.

Lacunas reproduzidas com dados inventados:

1. Se `requires_identity_review=False` e os checks gold/piloto forem `null`/`not_requested`, o resultado é `unassigned_development_NOT_a_train_split`. Não é uma prova de ausência de sobreposição. O preparador NER admite referências opcionais e pode produzir precisamente esse estado; a contagem do job 15216 não demonstra que as referências foram verificadas.
2. Uma linha com `label=null` e `labels=["ARGUIDO"]` é aceite como não anotada. O guard só inspeciona o campo escalar.
3. A CLI confronta o número de linhas com o manifesto, mas não verifica a associação dos IDs/documentos ao manifesto correspondente. O hash do input é registado apenas no plano produzido; não prova que foi usado o inventário certo.

Proposta antes da utilização 19c: manter checks não realizados numa reserva explícita ou recusar elegibilidade até os completar; rejeitar anotações prévias em ambos os formatos; validar IDs/documentos/contextos contra os artefactos do inventário e testar a CLI completa. Nunca declarar ausência de leakage por simples contagem ou igualdade de `process_group_id`. Não requer nova inferência NER nem alteração do inventário original.

### Qwen: preservar trabalho, sem o promover a protocolo atual

O protótipo reutiliza classes e helpers da Experiência 17, marking canónico, inferência offline, greedy, seed, quotes literais, parsing estrito, saída SILVER e `human_validated=false`. Oculta `suggested_label` no prompt. O wrapper respeita Slurm e usa `venv-ner`.

Porém, exige exatamente 40 candidatos e o validador de candidatos 19a, carrega a taxonomia histórica, coloca REFERENCE em `experimental_categories`, não aceita `other_roles` e calcula agregados dependentes de `suggested_label`. Não recebe diretamente o inventário completo sem sugestões. O default `revision=main` não fixa pesos imutáveis; não há resume. Os testes cobrem funções/schema, não carregamento, CLI completa, geração real ou compatibilidade com as menções do job 15216.

Não instalar pesos nem criar uma segunda arquitetura de anotação para aproveitar este protótipo. Manter as funções potencialmente reutilizáveis para experiências locais futuras; documentar a suspensão. Para a 19c, decidir o protocolo GPT/Claude, versão/schema v2 e controlo de privacidade antes de adaptar interfaces.

### Documentação operacional já rastreada

`docs/experiment_19b_ner_execution.md`, embora não estivesse modificado, ainda exige ficheiros privados antigos da 19a, indica g09 como nó de execução e não descreve o guard WordPiece do commit fc069e15. A dependência antiga foi removida em `86ecf19`; as referências 19a/gold/piloto são opcionais e explícitas no preparador. A documentação deve ser corrigida numa alteração separada e testada quanto a links/comandos, sem voltar a executar NER.

Evitar confundir o ponto de acesso g09 com o nó de execução autorizado pelo Slurm. A existência de SSH não autoriza GPU fora de alocação. Não atualizar tempos/versões/recursos dos jobs remotos sem os respetivos relatórios.

As sobreposições entre documentos de estado e relatórios são sobretudo história e não código duplicado a eliminar. Consolidar a orientação atual em THESIS_STATE/DECISIONS e acrescentar avisos/links aos snapshots; preservar os números e a fonte de cada ensaio. O helper de proteção de outputs do Qwen duplica funcionalidade já existente; não justifica refatoração agora, enquanto o protótipo está suspenso.

## Privacidade e ficheiros que não devem entrar no Git

Revisão dos 16 ficheiros pendentes: não foram encontrados nomes de pessoas conhecidos dos controlos privados, fragmentos dos contextos privados, nomes de ficheiros-fonte reais, emails, chaves privadas ou padrões de tokens/credenciais. A comparação local utilizou seis artefactos de controlo, 290 superfícies de nomes e 1.030 fragmentos de contexto, sem publicar nenhum deles. Os testes inspecionados usam texto inventado. Referências a caminhos genéricos privados e hashes não incluem o seu conteúdo.

Isto é uma verificação limitada: não certifica ausência de qualquer dado pessoal ou segredo desconhecido. Não houve acesso ao inventário integral remoto para ampliar essa comparação; não usar o resultado como garantia de anonimização. Todos os ficheiros continuam sujeitos a revisão do diff antes de um futuro commit.

Não versionar: corpus original, JSONL de candidatos/menções/previsões/labels SILVER, revisões individuais, mapas reversíveis, manifestos privados, planos de lotes com IDs, logs Slurm ou outros outputs com texto, modelos, checkpoints, caches, credenciais e ambientes. Mesmo o export pseudonimizado permanece privado até inspeção/autorização. `data/raw/`, `models/`, `venv/` e `venv-ner/` continuam ignorados; nenhum desses conteúdos aparece no status pendente.

Os sete relatórios pendentes em `results/` contêm agregados e referências históricas, não datasets privados. A recomendação de manter não abrange os relatórios remotos dos jobs 15209/15215/15216: serão tratados separadamente. O hash do gold50 foi reconfirmado: `f687174287e7aeb50283a42e510897eb4bd9daa663749b3f3a4507c77a3bd6c8`.

## Verificação realizada

- `venv/Scripts/python.exe -m unittest discover -s tests -v`: **119 testes**, sucesso, **1 integração opcional omitida**. Não foi carregado o modelo Eduardo nem Qwen.
- Testes Qwen: **9/9**; lotes: **3/3**, executados também separadamente.
- Checkout temporário isolado com código rastreado e os cinco ficheiros pendentes de código/testes/wrapper, sem datasets privados nem modelos: **119 testes**, sucesso, **1 integração opcional omitida**. Confirma ausência de dependências privadas na suite, não dispensa inputs privados explícitos nas execuções reais.
- `--help` dos dois scripts: sucesso, sem leitura de dados privados ou inferência.
- `bash -n scripts/slurm/run_qwen3_19b.sbatch`: sucesso com o Bash do Git local; não valida recursos/ambiente remotos.
- Experimentos sintéticos de revisão reproduziram os dois comportamentos de reserva/labels acima; não são regressões corrigidas nem testes novos adicionados.
- Links locais da documentação criada/atualizada e `git diff --check`: sucesso. Hashes do pool/auditoria v5, lote de 40, dez revisões e gold50 conferidos sem alterações. Index Git vazio; nenhuma alteração staged.

## Proposta de commits — nenhum executado

| Ordem | Mensagem em inglês | Âmbito e condição |
| --- | --- | --- |
| 1 | `Harden private annotation batch planning for full-corpus inventories` | Planeador e testes correspondentes, depois de corrigir/testar as lacunas identificadas. Não apresentar este patch como já implementado. |
| 2 | `Preserve the suspended Qwen silver annotation prototype` | Script Qwen, nove testes, wrapper e respetiva documentação, com aviso histórico/suspenso e sem o promover a anotador 19c. Pode ser adiado sem bloquear a 19c. |
| 3 | `Record aggregate Experiment 19a and 19b preparation reports` | Sete relatórios locais agregados, conservando resultados históricos e qualificando plan02/412/full01. Não incluir relatórios Slurm ainda não revistos. |
| 4 | `Document completed STJ NER extraction and Experiment 19c priorities` | THESIS_STATE, DECISIONS, esta revisão, documentação do exportador e correções do guia NER. Fonte do job 15216 atribuída ao utilizador; sem alterações na pipeline. |

Antes de cada commit futuro: selecionar paths explicitamente, rever o diff staged e repetir os checks apropriados. Não usar `git add .`. Esta proposta aguarda revisão do utilizador; não há autorização nesta fase para commit, push, envio externo ou arranque da 19c.
