# Estado persistente da tese

Atualizado em **16-11-2026**. Este ficheiro distingue resultados existentes, funcionalidades implementadas e trabalho pendente. Não contém excertos nem dados pessoais dos acórdãos.

## Atualização mais recente: Experiência 19c — piloto Qwen autorizado

**Nova evidência comunicada pelo utilizador:** as três pendências são GOLD, de dois acórdãos cujos textos originais foram obtidos; os três contextos aparecem integralmente neles. O parser no g09 rejeitou a identidade externa. Confirmadas no código duas causas: posições numéricas não aceitam letras e o valor do cabeçalho não era reconhecido na linha seguinte. Não se confirmou qualquer substituição S/5 nem se leram os originais privados neste workspace.

Implementados cabeçalhos multilinha com diagnóstico de tokens não-canónicos e [wizard privado DGSI](../src/annotation/prepare_dgsi_adjudication_19c.py), ligando cópia intacta, captura oficial local, URL, ID confirmado e fingerprints. Sem heurística de renumeração. `validate_decision` continua obrigatório; identidades que correspondam ao corpus originam reservas, não exclusões como externas. [Comando único, seleção e Slurm](experiment_19c_dgsi_evidence.md). O desbloqueio real continua dependente da execução e das evidências no INESC; não há resultado Qwen novo.

Validação local DGSI: **181 testes**, sucesso, **1 integração opcional omitida**; **13 novos**, incluindo três referências/dois originais sintéticos, confirmação de origem, ausência de substituição S/5, hashes/URLs contraditórios e proteção de famílias conhecidas.

**Preparação real comunicada posteriormente pelo utilizador:** no g09, o lote piloto01 ficou bloqueado: `selection_complete=false`, 0 selecionados, 111 referências protegidas, 108 resolvidas, 3 pendentes, 15 grupos bloqueados, `LLM_calls=0`. Não houve leitura desse manifesto privado no workspace Windows nem se afirma que as três pendências sejam todas GOLD ou tenham a mesma causa. Ainda não há 30 ocorrências selecionadas nem inferência Qwen real confirmada.

Implementado [diagnóstico 19c](../src/annotation/diagnose_pilot_protection_19c.py), com saída partilhável só de códigos/contagens/tokens HMAC e mapeamento/chave/evidência privados no INESC. A seleção v2 acrescenta apenas reconciliações positivas verificáveis (formatação, hash documental, formato processual com raiz existente); reserva todos os documentos/grupos correspondentes. Falta de match não prova ausência. Similaridade só sugere revisão e nunca resolve uma pendência. Adjudicação exige fingerprints e evidência; uma declaração simples já não é aceite. [Condições, comandos e limites](experiment_19c_protection_diagnostic.md). Testes são sintéticos; o diagnóstico real e eventual desbloqueio continuam por executar no g09.

Validação local desta correção: **168 testes**, sucesso, **1 integração opcional omitida**; **16 testes novos** do diagnóstico/proveniência. Incluem stdout seguro da CLI, reconciliação positiva que permite selecionar 30 num corpus inventado e manutenção da gate sem prova. Não substituem a leitura do manifesto no INESC.

O utilizador reviu a prioridade anterior GPT/Claude e autorizou **primeiro um piloto local Qwen3-8B de 30 ocorrências**, sem APIs, anotação massiva ou treino. Implementados [preparação](../src/annotation/prepare_stj_pilot_19c.py), [anotador](../src/annotation/annotate_stj_silver_19c.py), [prompt 19c-v1](../config/prompts/role_annotation_19c_v1.txt), [wrapper Slurm](../scripts/slurm/run_qwen3_19c_pilot.sbatch) e testes sintéticos. O loader offline é partilhado com o protótipo antigo; o modo histórico de 40 continua suspenso.

**Não executado no corpus real nesta sessão.** SSH não interativo recusou autenticação; não se confirmou o esquema efetivo no servidor, pesos/cache, ambiente ou recursos atuais, não se prepararam 30 registos reais nem se submeteram jobs. O contrato foi confirmado no produtor/validador existente e será obrigatoriamente validado no bundle remoto. [Comandos e limites](experiment_19c_qwen_pilot.md).

Fonte agregada entretanto disponível no commit preexistente **4b339d3**: [job 15216](../results/experiment_19b_ner_full_15216.md), consultado localmente, confirma as contagens finais e que os checks de reservas gold/piloto foram **`not_requested`**. Não são dados de treino automaticamente elegíveis. O agregado confirma a correção do caso 703 WordPieces (máximo seguro 486, uma subdivisão); não expõe os registos individuais. As referências históricas abaixo a relatórios apenas remotos antecedem a sua disponibilização local.

A preparação exige NER completo e referências protegidas verificadas por hash, conserva campos originais e faz nova verificação explícita de exclusões. Uma ocorrência por grupo relacionado, seleção determinística por variedade com seed 42, coorte exploratória nunca gold. Flags antigas desconhecidas não são apagadas; identidades conflitantes ou referências protegidas não resolvidas bloqueiam/excluem conforme o caso. Não garante UNKNOWN/REFERENCE ou equilíbrio por classe antes da anotação.

Taxonomia v2 de dez classes, multi-label, `other_roles`, evidência literal e âmbito. Zero-shot greedy FP16, checkpoint local imutável, input máximo 4096 tokens e 1024 novos, sem truncagem. Preflight GPU dos 30 é obrigatório antes da geração. Propostas sempre SILVER e `human_validated=false`; JSON inválido é conservado separadamente, nunca UNKNOWN. Preservar benchmarks, revisões, corpus e `silver.spacy`. Não inferir resultados de modelo a partir de testes com mocks. A implementação será versionada após validação; não autoriza envio externo.

Validação local 19c: **152 testes**, sucesso, **1 integração opcional omitida**; **18 testes novos** da 19c, incluindo loader offline mockado, reservas/IDs/offsets, parsing e preflight→30 gerações simuladas. Não substituem uma execução GPU real.

## Estado da consolidação anterior: NER integral concluído

**Confirmado pelo utilizador em 16-11-2026:** o job Slurm **15216**, no INESC, terminou **COMPLETED, ExitCode 0:0**, com NER de **191/191 textos distintos**, correspondentes a **388 documentos auditados**, **24.467 ocorrências PER aceites** e **24.977 previsões PER brutas**. `inventory_complete=True`, `NER_executed=True`, `LLM_calls=0`. São ocorrências previstas, não pessoas distintas nem labels jurídicas validadas. A diferença de 510 não deve ser atribuída a motivos de filtragem sem consultar os artefactos.

A correção do Transformer está no commit `fc069e15bac5d1638848efa3e2d782de23b86f56`: valida o limite efetivo de WordPieces, incluindo tokens especiais, e subdivide janelas excessivas com sobreposição, sem truncar o texto. Preserva os offsets e a persistência das previsões. Não alterar nem voltar a executar esta pipeline apenas para consolidar documentação ou preparar lotes.

**Fonte e limite:** as contagens acima foram fornecidas pelo utilizador; os relatórios dos jobs **15209, 15215 e 15216 estão apenas no g09** e serão tratados separadamente. Não foram consultados nesta revisão. Não se inferem duração, versões, VRAM utilizada, distribuição de papéis, causas de rejeição ou correção dos spans a partir dessas contagens. Os inventários recuperados de 384/412 e a extrapolação de ~27 mil permanecem históricos, não a dimensão atual.

Prioridades acordadas com o utilizador, em continuidade com a orientação atribuída ao professor Borbinha:

1. Preservar os outputs completos do job 15216; verificar manifestos, offsets, proveniência e reservas gold/piloto antes de preparar os lotes. Não reconstruir o inventário nem pressupor que os checks opcionais gold/piloto foram executados.
2. Preparar anotação assistida por **GPT/Claude**, sobre o universo completo de menções elegíveis, sem quotas de 40/430 e sem `suggested_label`. O procedimento concreto usado pelo professor ainda não foi fornecido; não inventar prompts, modelos ou acordos de tratamento de dados.
3. Separar planeamento privado, desidentificação, inspeção de privacidade e autorização de transmissão. A pseudonimização reversível não certifica anonimização. Nenhum envio externo é autorizado por esta consolidação.
4. Guardar propostas como **SILVER**, multi-label, com evidência, âmbito, incerteza e `other_roles`; nunca `human_validated=true` automaticamente. UNKNOWN e REFERENCE precisam de cobertura observada após anotação, não de labels fabricadas pelo NER.
5. Conservar as labels específicas e derivar agrupadas sobre os mesmos exemplos/splits, isolando documentos duplicados, aliases e processos relacionados. O benchmark gold50 e as dez revisões piloto permanecem protegidos.

Qwen permanece suspenso como anotador: o protótipo histórico exige 40 candidatos, usa REFERENCE separada e não suporta `other_roles`; não é o executável da 19c. O planeador privado foi corrigido: checks ausentes/indeterminados ficam em revisão, reservas propagam-se por documento/hash/bloco/processo/aliases, e labels pré-preenchidas escalares/múltiplas ou propostas SILVER são recusadas. Não cria splits nem estabelece elegibilidade de treino. Ver [revisão de consolidação](experiment_19c_consolidation_review.md).

O planeador valida o bundle do mesmo prefixo (manifesto, documentos, menções e previsões no caso NER), IDs derivados de hash/offsets, contextos e fontes originais pelos fingerprints do manifesto. Regista hashes de todos os inputs verificados no novo plano privado. Precisa das fontes nos caminhos registados; falha explicitamente se faltarem/mudarem. Não basta copiar só o JSONL/manifesto nem reconhecer `--allow-partial` para dispensar proveniência. Esta validação não executa NER nem autentica um bundle integralmente falsificado.

Verificação local da consolidação autorizada: **134 testes**, com **1 integração opcional omitida**; testes Qwen **9/9**, lotes **18/18**, CLIs `--help` e sintaxe Bash dos wrappers aprovados. Foram autorizados commits separados e push após validação, ao contrário da primeira revisão. Sem inferência, treino, downloads, submissões Slurm, acesso aos relatórios remotos ou início da 19c. `data/raw/silver.spacy`, datasets e revisões preservados. Os blocos seguintes conservam o percurso histórico; não usar os seus próximos passos como backlog atual.

## Objetivo e arquitetura

Estudar a classificação contextual de papéis jurídicos de pessoas como extensão de um sistema de anonimização de acórdãos portugueses:

```text
Text -> Eduardo NER -> PER -> classificador de papéis
```

O pipeline spaCy preferido está em `models/eduardo_extended_model` (local, ignorado pelo Git), proveniente do modelo extended de Eduardo. Tem componentes `transformer` e `ner`, com backbone BERTimbau; as labels NER observadas são PER, ORG, LOC, DAT, IDP e MOR. Labels NER e papéis jurídicos são camadas diferentes. Existem avisos de compatibilidade entre o modelo herdado e bibliotecas mais recentes; carregar com sucesso não demonstra equivalência de precisão.

Fontes: [notas do modelo](old_models/model_notes.md), [pipeline](../src/evaluation/pipeline_roles.py), [extrator atual](../src/data/extract_role_candidates_v2.py).

## Taxonomias

**Histórica, experiências até 18:** ARGUIDO, TESTEMUNHA, RELATOR, REU, UNKNOWN. Classificação de uma pessoa marcada por exemplo. ARGUIDO corresponde ao acusado criminal e REU ao réu civil. Esta taxonomia continua a reger o conjunto congelado de 50 exemplos.

**Histórica da Experiência 19:** nove classes em [config/role_taxonomy.json](../config/role_taxonomy.json), preservadas para reprodução. **Operacional desde 11-11-2026, para 19b/19c:** ARGUIDO, REU, AUTOR, REQUERENTE, RECORRENTE, RECORRIDO, TESTEMUNHA, RELATOR, REFERENCE, UNKNOWN, em [config/role_taxonomy_v2.json](../config/role_taxonomy_v2.json).

| Papéis finos | Classe agregada derivada |
| --- | --- |
| ARGUIDO, REU | PASSIVE_PARTY |
| AUTOR, REQUERENTE | ACTIVE_PARTY |
| RECORRENTE | APPELLANT |
| RECORRIDO | APPELLEE |
| TESTEMUNHA | WITNESS |
| RELATOR | RAPPORTEUR |
| REFERENCE | REFERENCE |
| UNKNOWN | UNKNOWN |

A anotação fina é a fonte de verdade. A agregação é automática, incluindo remoção determinística de duplicados em multi-label. Comparações fina/agregada exigem os mesmos exemplos e splits. A taxonomia final continua sujeita a validação científica e institucional.

## Experiências 13–19: resultados confirmados nos ficheiros

As métricas abaixo foram verificadas nos artefactos existentes; não foram produzidas novas experiências nesta atualização. Accuracy e macro-F1 têm escala 0–1. Não comparar linhas como se tivessem o mesmo dataset, tamanho e protocolo.

| Experiência | Avaliação / método | Accuracy | Macro-F1 | Fonte |
| --- | --- | --- | --- | --- |
| 13 | 240 exemplos `realistic_v2`, BGE-M3 + LR | 0.5417 | 0.5210 | [relatório](../results/experiment_13_encoder_comparison.txt) |
| 13 | Mesmo benchmark, multilingual-e5-base + LR | 0.4917 | 0.4596 | [relatório](../results/experiment_13_encoder_comparison.txt) |
| 13 | Mesmo benchmark, multilingual MPNet + LR | 0.4042 | 0.3755 | [relatório](../results/experiment_13_encoder_comparison.txt) |
| 13b | 240 exemplos, espaçamento corrigido em memória, BGE-M3 + LR | 0.5375 | 0.5171 | [relatório](../results/experiment_13b_encoder_comparison_corrected_markers.txt) |
| 13b | Mesmo rerun, multilingual-e5-base + LR | 0.5000 | 0.4677 | [relatório](../results/experiment_13b_encoder_comparison_corrected_markers.txt) |
| 13b | Mesmo rerun, multilingual MPNet + LR | 0.4000 | 0.3717 | [relatório](../results/experiment_13b_encoder_comparison_corrected_markers.txt) |
| 14 | Análise de erros BGE-M3 no benchmark de 240 | 0.5417 | 0.5210 | [relatório](../results/experiment_14_bge_m3_error_analysis.txt) |
| 15 | Smoke test preliminar de 10 exemplos reais, BGE-M3 + LR | 0.6000 | 0.4743 | [relatório](../results/experiment_15_bge_m3_real_smoke_test.txt) |
| 16 | Primeira avaliação nos 50 reais congelados, regras entity-aware | 0.5000 | 0.4547 | [relatório](../results/experiment_16_real_stj_evaluation_v1.txt) |
| 16 | Mesmos 50, BGE-M3 + LR | 0.4800 | 0.3960 | [relatório](../results/experiment_16_real_stj_evaluation_v1.txt) |
| 17 | Mesmos 50, Qwen3-8B zero-shot | 0.9800 | 0.9799 | [relatório](../results/experiment_17_qwen3_8b_real_stj.txt) |
| 17 | Mesmos 50, Qwen3-8B five-shot | 0.8000 | 0.7949 | [relatório](../results/experiment_17_qwen3_8b_real_stj.txt) |
| 18 | Mesmos 50, apenas BGE-M3 + LR | 0.4800 | 0.3960 | [relatório](../results/experiment_18_real_encoder_comparison.txt) |
| 19 | Comparação fina/agregada: infraestrutura e plano | — | — | [plano](../results/experiment_19_plan.txt) |

Contexto necessário:

- O benchmark `roles_eval_realistic_v2.jsonl` tem 240 exemplos gerados; não é o conjunto real do STJ. O resultado anterior menor em [experiment_13_compare_multiple_encoders.txt](../results/experiment_13_compare_multiple_encoders.txt) favorece MPNet e não deve ser confundido com o benchmark de 240.
- Nos scripts de embeddings, o treino é `data/processed/roles_v4.jsonl` (1328 exemplos), com `LogisticRegression(max_iter=2000)` sobre embeddings congelados de SentenceTransformers. Experiência 18 contém apenas BGE-M3. Referências: [13](../src/training/compare_embedding_models.py), [13b](../src/training/compare_embedding_models_13b.py), [18](../src/training/compare_embedding_models_real.py).
- A Experiência 13b corrigiu em memória 60 exemplos com markers sem espaços; 180 já eram canónicos. O dataset e os resultados 13 foram preservados.
- A Experiência 15 é preliminar. O caminho de avaliação foi posteriormente ampliado para 50; o seu script exige 10. O ficheiro atual não reconstitui automaticamente o snapshot daquele ensaio.
- A Experiência 17 está executada, apesar de bloqueios locais mencionados em fases anteriores. O [JSON de resultados](../results/experiment_17_qwen3_8b_real_stj_predictions.json) regista Linux/CUDA, Quadro RTX 6000, 50 exemplos, zero-shot com 0 outputs inválidos e five-shot com 1. Usa geração sem sampling, temperatura 0, thinking desativado e cinco demonstrações fixas de treino; os exemplos reais não são demonstrações. Fontes: [script](../src/evaluation/evaluate_qwen3_8b_real_stj.py), [scripts Slurm](../scripts/slurm/run_qwen3_full.sbatch).
- O desafio multi-entidade tem apenas 5 exemplos e fica separado dos resultados principais. O artefacto 16 regista accuracy 0.40 para regras e 0.00 para BGE-M3. O [diagnóstico Qwen](../results/qwen3_8b_multi_entity_diagnostic_v1.json) regista 0.60 zero-shot e 0.40 few-shot. São diagnósticos qualitativos.
- Existem relatórios e JSON de previsões das experiências 16/17. Para nova documentação, extrair apenas métricas/metadados; não republicar pessoas ou passagens desses ficheiros.
- O README e `docs/next_steps.md` contêm conclusões/numerações históricas. Não representam o ranking ou backlog atual. Os tempos de ambientes diferentes não constituem uma comparação controlada de desempenho.

## Conjunto real congelado

`data/eval/roles_eval_real_candidates_v1.jsonl`: **50 exemplos, 10 por classe histórica, todos human-validated**. Verificação em 30-10-2026:

```text
SHA-256: f687174287e7aeb50283a42e510897eb4bd9daa663749b3f3a4507c77a3bd6c8
```

Preservar este conjunto e os resultados anteriores. Não o utilizar como treino, seed de extração ou demonstração few-shot. Texto real permanece contínuo, sem markers inseridos; o alvo é identificado por offsets Python. Usar [entity_marking.py](../src/utils/entity_marking.py) para gerar a representação `[ENTITY] entity [/ENTITY]` na avaliação.

## Experiência 19 / 19a: acórdãos reais e anotação humana

**Implementado:** [mapeamento de taxonomias](../src/data/map_role_taxonomy.py), [validador fino](../src/evaluation/validate_role_dataset.py), [extrator de candidatos](../src/data/extract_role_candidates_v2.py), [validador de candidatos](../src/evaluation/validate_role_candidates_v2.py), [auditoria de proveniência](../src/data/role_provenance.py) e [revisor interativo local](../src/annotation/review_role_candidates.py). **Não há resultados de modelos para a comparação fina versus agregada.**

O extrator usa apenas PER do NER Eduardo como alvos e âncoras lexicais como sugestões. Filtra spans manifestamente falsos/mesclados sem inventar divisões, conserva offsets do documento e do contexto, audita cobertura por papel e privilegia diversidade de processos. Tem janelas limitadas, `nlp.pipe`, cache em memória de entradas exatamente iguais, progresso periódico, temporização por fase e `--max-documents`. `--output` e `--audit-json` na mesma execução evitam repetir NER.

Percurso confirmado, sem confundir as etapas:

1. Pool inicial por heurísticas: 220 candidatos de um corpus referido de 388 ficheiros texto; piloto revelou entidades falsas. Não é um benchmark gold.
2. Piloto NER v4: 10 documentos processados, **61 candidatos**. Dez candidatos revistos: **10 aceites, 0 rejeitados, 2 multi-label**, com 12 atribuições: ARGUIDO 4, RECORRENTE 4, TESTEMUNHA 1, RELATOR 2, UNKNOWN 1. Isto não mede precisão global do NER nem classificação automática.
3. No audit v4, NER consumiu aproximadamente 315.63s e o processamento total 331.60s, incluindo carregamento de cerca de 15.41s. Trata-se da execução guardada, não do novo benchmark GPU. O relatório enumera 392 ficheiros detetados de todas as extensões; não assumir que são 392 acórdãos ou processos independentes.
4. Proveniência e protocolo mention-level foram acrescentados depois. Os candidatos e as dez revisões v4 continuam preservados; não presumir que já têm todos os novos campos ou que foram readjudicados.

Fontes locais ignoradas, consultadas apenas para contagens/metadados: `data/raw/experiment_19a_audit_v4_smoke10.json`, `data/raw/experiment_19a_candidates_v4_smoke10.jsonl`, `data/raw/experiment_19a_v4_smoke10_reviews.jsonl`. Fontes versionáveis: [plano 19a](../results/experiment_19a_candidate_pool_plan.txt), [relatório de proveniência](../results/experiment_19a_provenance_report.txt), [protocolo](experiment_19a_annotation_protocol.md).

Pontos metodológicos em vigor:

- A tarefa é **mention-level**, com multi-label. Papéis em processos citados são admissíveis se suportados pelo contexto, mas devem ser assinalados por label; não estabelecem o papel no processo atual.
- UNKNOWN é uma pessoa válida sem papel-alvo suportado; REJECT indica entidade/span/exemplo incorreto ou inutilizável; uncertain fica sem validação. Apenas confirmação explícita de uma anotação aceite define `human_validated=true`.
- Evidência nova: explicit, implicit ou not_applicable para UNKNOWN; uncertain para decisões pendentes. A dificuldade e os distractores são campos separados. Revisões antigas não são migradas automaticamente.
- AUTOR é o demandante civil, não o autor de um crime ou de uma obra. Atribuir ARGUIDO também exige suporte contextual.
- REU continua com uma lacuna no piloto: 8 âncoras, 0 candidatos descobertos/selecionados. A fase anterior à seleção precisa de inspeção; não inventar exemplos para preencher quotas.
- Houve conflito entre IDs exatos de cabeçalho e filename com sufixos `.S1`/`.S2`. Conservar ambas as evidências e não adjudicar automaticamente. `process_group_id` agrupa a base para splits; não prova identidade da decisão. Resolver grupos desconhecidos e conflitos antes de uma avaliação com splits.
- Martim: o segmentador documental será avaliado separadamente, depois do baseline de taxonomia. Não está marcado como integrado ou avaliado.

## Ambiente NER e GPU

O ambiente dedicado de trabalho para NER/GPU é **`venv-ner/`**, ignorado pelo Git. O `venv/` histórico também existe; não os tratar como intercambiáveis nem presumir CUDA pela presença de uma GPU física.

**Teste funcional GPU concluído:** confirmação do utilizador nesta sessão, em 30-10-2026. O código exige `spacy.require_gpu(gpu_id)` antes de `spacy.load()` quando recebe `--gpu-id`; sem argumento, exige CPU. O stdout identifica o dispositivo. Os [testes de seleção de dispositivo](../tests/test_role_candidate_device.py) usam mocks; não são a prova da execução GPU real.

Limite da evidência de 30-10-2026: `venv-ner/pyvenv.cfg` não estava presente neste checkout e não foi localizado um relatório autónomo com versões/tempos desse teste funcional. Em 16-11-2026, este checkout dispõe apenas do Python `venv/Scripts/python.exe` usado nos testes; o NER integral remoto foi entretanto confirmado pelo utilizador. Não se registam versões ou aceleração inventadas. `requirements.txt` não é um lockfile comprovado do ambiente GPU; os detalhes do job 15216 aguardam os artefactos remotos.

## Backlog histórico de 30-10-2026 — superado pelo estado atual acima

Preservado para rastreabilidade. Não repetir o benchmark ou a extração integral como pré-condição da 19c; o job 15216 já concluiu essa etapa.

1. Confirmar o Python do ambiente `venv-ner` usado no teste funcional e registar versões de spaCy, spacy-transformers, PyTorch e suporte CUDA/CuPy; não reinstalar automaticamente dependências numa tarefa documental.
2. Rever a auditoria de IDs sem NER e os conflitos de proveniência, preservando a evidência original.
3. **Executar um benchmark GPU determinístico de 10 documentos**, guardando pool, audit JSON, stdout com dispositivo e tempo de parede numa só passagem. Confirmar qualidade/offsets, cobertura AUTOR/REU e consistência dos grupos antes de extrapolar.
4. Só depois planear a extração completa, com novos nomes de ficheiros, auditoria e validação humana. A extração completa com a versão atual não está marcada como concluída.
5. Consolidar uma nova coleção humana de cerca de 10–12 exemplos por papel fino, rever quotas e separar grupos processuais antes dos splits. Realizar então a comparação fina/agregada; não há métricas dessa comparação ainda.

Exemplo de benchmark futuro a executar manualmente na raiz, depois de confirmar o ambiente e a proveniência. Os outputs têm um nome novo e a ferramenta recusa ficheiros existentes:

```powershell
Measure-Command {
    & .\venv-ner\Scripts\python.exe -u src/data/extract_role_candidates_v2.py `
        --input-dir data/raw/iris/naoanomimizados_txt `
        --ner-model models/eduardo_extended_model --gpu-id 0 `
        --ner-batch-size 4 --cpu-threads 4 `
        --max-documents 10 --progress-seconds 5 `
        --max-per-role 30 --context-chars 240 `
        --hard-share 0.25 --max-per-process-role 2 `
        --output data/raw/experiment_19a_v6_gpu_bench10_candidates.jsonl `
        --audit-json data/raw/experiment_19a_v6_gpu_bench10_audit.json `
        | Tee-Object -FilePath data/raw/experiment_19a_v6_gpu_bench10_stdout.log | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark falhou; consultar o stdout e a auditoria.' }
} | Select-Object TotalSeconds

.\venv-ner\Scripts\python.exe src/evaluation/validate_role_candidates_v2.py `
    data/raw/experiment_19a_v6_gpu_bench10_candidates.jsonl
```

O exemplo não foi executado nesta sessão. Escolher também um nome novo para o log se já existir; `Tee-Object` não tem a proteção de não sobrescrita do extrator. Não repetir uma auditoria NER completa e depois a mesma extração apenas para obter dois outputs.

## Novo requisito: autores de citações — 30-10-2026

**Nota atual:** o texto seguinte regista o requisito inicial. Desde 11-11-2026, REFERENCE é a classe principal adotada na taxonomia v2; CITATION_AUTHOR não foi adotado como nome de label. A autorização de classificar não resolve a política de preservação de identidades.

**Pendente, ainda não implementado:** distinguir pessoas que são autoras de obras/artigos citados no texto. A designação de trabalho é **CITATION_AUTHOR**. Não é AUTOR processual e não deve ser confundida conceptualmente com UNKNOWN.

Não foi acrescentada a `config/role_taxonomy.json`, aos mapeamentos, aos modelos, aos prompts ou aos datasets. É necessário definir se será label, atributo ou outra camada e como se relacionará com os papéis processuais, incluindo pessoas que acumulam funções. Os códigos atuais e as anotações históricas permanecem preservados; não recodificar UNKNOWN automaticamente.

A eventual aplicação é uma **sugestão de exclusão da anonimização**, não uma regra automática de preservação de nomes. A taxonomia final, os critérios de evidência e as regras de preservação/anonimização exigem validação com os orientadores e o STJ. Falta desenhar exemplos seguros, anotação, avaliação e tratamento da incerteza. Nenhuma dessas etapas está concluída.

## Limitações científicas e privacidade

- O conjunto real é pequeno e equilibrado artificialmente; 10 exemplos/classe não permitem generalizar o resultado 0.98 para acórdãos longos ou para o corpus inteiro.
- Os 50 exemplos avaliam classificação condicionada ao alvo/contexto, não a qualidade do pipeline de anonimização ponta a ponta. O recall do NER e as entidades que nem chegam ao classificador também importam.
- O domínio sintético difere dos acórdãos; âncoras lexicais e rejeições conservadoras introduzem viés de seleção. A aceitação de dez candidatos não estima precisão/recall do extrator.
- Identidade do processo, casos citados, texto repetido e versões de documentos podem provocar leakage. O congelamento local não certifica ausência de exposição de fontes públicas no pré-treino de LLMs.
- Tempos dependem de hardware, ambiente, carga, warm-up e cache; o teste funcional GPU e microbenchmarks sintéticos não estabelecem aceleração real.
- Nunca colocar dados pessoais de acórdãos, documentos brutos, notas privadas, modelos ou checkpoints no Git. Corpus/pools/revisões/auditorias ficam em `data/raw/`; modelos e ambientes ficam ignorados. Não reproduzir conteúdo de artefactos antigos como se estivesse automaticamente autorizado para publicação.
- Papéis jurídicos e a futura categoria de autor citado não decidem, por si, a política de anonimização. A decisão institucional exige validação dos orientadores e do STJ.

## Fontes e manutenção

Fontes principais: configuração de taxonomia; scripts 13–18 e extração/anotação/proveniência; relatórios e JSON de métricas referidos acima; protocolo 19a; plano 19 e relatório de proveniência; `.gitignore`, `requirements.txt`, scripts Slurm e testes em `tests/`. A confirmação GPU e o requisito CITATION_AUTHOR provêm do pedido do utilizador de 30-10-2026, com o grau de verificação indicado.

Verificação de 30-10-2026: `venv/Scripts/python.exe -m unittest discover -s tests` executou 66 testes com sucesso. As referências Markdown locais foram verificadas e o hash do conjunto congelado foi confirmado. Não houve nova inferência, treino ou execução GPU nesta sessão.

Alterações desta sessão são documentais. Ver [DECISIONS.md](DECISIONS.md) para os compromissos metodológicos e [AGENTS.md](../AGENTS.md) para instruções operacionais. Atualizar estado com fonte, data e distinção entre planeado, implementado e medido; nunca preencher lacunas com resultados presumidos.

## Atualização posterior: lote 19a e preparação 19b — 30-10-2026

Esta atualização sucede ao backlog histórico acima: o pool v5 completo foi auditado e foi preparado um lote de 40 candidatos, cinco por sugestão, 40 grupos/hashes distintos. Ver [auditoria v5](../results/experiment_19a_v5_gpu_full_annotation_audit.md) e [relatório do lote](../results/experiment_19a_annotation_batch01_v1_report.md). O lote privado permanece por anotar; sugestões não são gold.

A Experiência 19b implementa propostas SILVER Qwen3-8B zero-shot com evidência/âmbito, multi-label e abstenção, sem enviar suggested_label. REFERENCE é categoria experimental separada, não alteração da taxonomia fina nem política de preservação de identidades. Nenhuma saída é human-validated. O [protocolo 19b](experiment_19b_silver_annotation.md) contém implementação, comandos Slurm e limitações.

Verificação atual: 81 testes sintéticos passaram. Tentativa de smoke com cinco candidatos bloqueada no pré-flight por `cuda_unavailable`: PyTorch 2.11.0+cpu, Transformers 4.53.2; cache local com metadados/tokenizer mas sem ficheiros de pesos Qwen. Zero inferências e nenhum dataset SILVER produzido. [Resultado agregado](../results/experiment_19b_smoke01_aggregate.md). Não foi confirmado acesso INESC nem submetido job; o próximo passo é smoke real num ambiente autorizado com GPU/pesos, depois os 40 se a gate de parsing passar. Não existem resultados de qualidade/accuracy/F1 da Experiência 19b. Dados originais, revisões piloto e gold50 preservados.

### Orientação posterior: decidir a anotação antes de executar Qwen

O utilizador confirmou acesso INESC anteriormente usado e ambiente remoto `venv-ner` CUDA; não usar o `venv` Windows para essa inferência. Porém, SSH e DNS desta sessão não resolveram o hostname fornecido, pelo que ambiente remoto, Slurm, GPUs e pesos continuam **não verificados nesta sessão**. Não se submeteu job nem descarregou modelo. O template foi corrigido para `venv-ner`, exige Slurm e respeita `CUDA_VISIBLE_DEVICES` do scheduler.

Próximo passo revisto: documentar o procedimento de anotação GPT/Claude referido pelo utilizador e decidir ferramenta, privacidade, prompt e validação, separadamente das experiências locais Qwen. Qwen/19b fica preparado, sem instalação ou inferência enquanto essa estratégia não for decidida e a execução não for confirmada. Estão preparados [comandos de inspeção apenas de leitura](experiment_19b_silver_annotation.md); não assumir acesso SSH como autorização para usar GPUs diretamente.

### Piloto de exportação externa — Qwen temporariamente suspenso

Por orientação posterior, priorizar ChatGPT/Claude; suspender temporariamente a execução Qwen. O exportador local preparou os cinco primeiros registos do lote, em CPU com Eduardo NER, sem inferência de papéis ou envio externo. Há JSONL transformado, tarefa/schema e mapa reversível privado em `data/raw/experiment_19b_external_pilot01_*`; apenas [validação agregada](../results/experiment_19b_external_pilot01_export_validation.md) é versionável.

Foram confirmados 5/5 offsets e 5/5 reconstruções exatas, input intacto e contagens de âncoras preservadas. A saída é pseudonimizada e requer inspeção humana de privacidade/contexto, não anonimização certificada. IDs internos/proveniência ficam no mapa; nenhum suggested_label é exportado. Nada foi partilhado nem anotado; não existe novo gold. Ver [comandos e limites](external_annotation_export.md).

### Exportação integral posterior: 40 candidatos

O exportador foi ampliado para 40 por omissão e gerou `data/raw/experiment_19b_external_full01_input.jsonl`, acompanhado de manifesto privado reversível e tarefa/schema. Os 40 IDs, offsets e reconstruções foram verificados, com âncoras preservadas e 92 testes aprovados. Piloto anterior, datasets e revisões intactos. [Validação integral](../results/experiment_19b_external_full01_export_validation.md).

Os padrões diretos de identificadores não encontraram correspondências residuais. Um alerta de capitalização é concatenação de pseudónimos gerados em EXEMPLO_018, a rever por legibilidade; riscos contextuais/omissões NER continuam a exigir inspeção antes de partilhar. Saída sem suggested_label, não certificada como anónima. Qwen permanece suspenso; sem envio externo, anotação ou treino.

### Estratégia posterior: corpus completo, não amostra 40/430

O universo passa a ser os 191 textos distintos dos 388 ficheiros. Planeamento local confirmou 15.102.124 caracteres, 2.411.871 palavras por whitespace e 187 blocos conservadores de split; 47 textos têm conflitos/cardinalidade de raízes a rever. O NER antigo cobria 63,81% do texto único e não persistia todos os spans. Recuperaram-se 384 ocorrências do pool, preservando nove variantes de contexto múltiplo; **não é inventário completo**.

Artefactos privados canónicos: `data/raw/experiment_19b_corpus_plan02_*`. [Relatório agregado](../results/experiment_19b_corpus_plan02.md) contém estimativa operacional condicional (~27 mil menções, não medição), cenários de volume, comandos e limites. Total real de PER continua null até execução integral. O novo preparador usa cobertura sem âncoras/quotas com `--run-ner` explícito e persiste previsões através de um callback opcional no detetor existente. Não foi feita essa execução, anotação, transmissão ou treino. 100 testes passaram; Qwen continua suspenso e os lotes anteriores são apenas artefactos históricos, não limites do universo.

## Retoma TESE V2 — 11-11-2026

Reverificados os 388 ficheiros/191 textos e metadados sem nova inferência. Além das 384 ocorrências recuperadas do pool, reutilizaram-se 28 PER adicionais do cache privado dos 40 contextos; 40 previsões já existiam e uma variante sobreposta ficou em revisão. Inventário recuperado **412 ocorrências, ainda parcial**, com offsets/documento/contexto e sem suggested_label. Não há cache NER completo recuperável; um DocBin adicional tem zero correspondências exatas por hash com o corpus. Total completo continua desconhecido.

Novos artefactos privados: `data/raw/experiment_19b_corpus_recovered_20261111_v1_*`; seis planos parciais de lotes em `data/raw/experiment_19b_batches_RECOVERED_PARTIAL_20261111_v1/`. Os planos incluem todos os 412 IDs, sem texto partilhável; coortes de reserva/proveniência não são splits. O planeador recusa um inventário parcial por omissão. [Relatório atual e comandos](../results/experiment_19b_corpus_inventory_20261111.md).

106 testes passaram. UNKNOWN/REFERENCE continuam sem cobertura demonstrada no inventário recuperado enviesado por âncoras; a passagem integral já preparada é necessária para incluir ocorrências fora dessas regiões. Não houve API, SSH, download, treino, nova inferência NER, transmissão ou anotação LLM. Próximo passo: teste técnico limitado em alocação Slurm autorizada e, depois, NER integral sem quotas, seguido de desidentificação/inspeção antes da eventual anotação externa. Qwen permanece suspenso, gold50 e revisões preservados.

### Preparação da execução Slurm — registo histórico de 11-11-2026

O utilizador quer executar smoke de três documentos e depois os 191 textos no g09. Foram revistos o preparador e criado um wrapper Slurm, com gate de smoke, heartbeat, metadados e sem novo ficheiro known_mentions_PARTIAL na inferência. Todas as previsões PER ficam guardadas, inclusive filtradas; as válidas incluem contexto e ID, além da saída de menções aceites. [Instruções SSH/Slurm](experiment_19b_ner_execution.md).

Taxonomia principal solicitada: dez classes, incluindo REFERENCE, em `config/role_taxonomy_v2.json`, preservando o ficheiro histórico. A tarefa suporta labels multi-label específicas e other_roles com evidência/âmbito. A agregação será derivada sem reanotação nem perda da anotação fina. 108 testes e bash -n passaram. Nenhum novo inventário, NER ou treino foi executado nesta revisão; a tentativa SSH de leitura falhou no DNS, logo recursos/partição remotos não foram confirmados e nenhum job foi submetido. Prioridade restante: NER integral → inspeção/desidentificação → anotação GPT/Claude SILVER → comparação específica/agrupada; Qwen continua suspenso.
