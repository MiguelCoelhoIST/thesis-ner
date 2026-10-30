# Estado persistente da tese

Atualizado em **30-10-2026**. Este ficheiro distingue resultados existentes, funcionalidades implementadas e trabalho pendente. Não contém excertos nem dados pessoais dos acórdãos.

## Objetivo e arquitetura

Estudar a classificação contextual de papéis jurídicos de pessoas como extensão de um sistema de anonimização de acórdãos portugueses:

```text
Text -> Eduardo NER -> PER -> classificador de papéis
```

O pipeline spaCy preferido está em `models/eduardo_extended_model` (local, ignorado pelo Git), proveniente do modelo extended de Eduardo. Tem componentes `transformer` e `ner`, com backbone BERTimbau; as labels NER observadas são PER, ORG, LOC, DAT, IDP e MOR. Labels NER e papéis jurídicos são camadas diferentes. Existem avisos de compatibilidade entre o modelo herdado e bibliotecas mais recentes; carregar com sucesso não demonstra equivalência de precisão.

Fontes: [notas do modelo](old_models/model_notes.md), [pipeline](../src/evaluation/pipeline_roles.py), [extrator atual](../src/data/extract_role_candidates_v2.py).

## Taxonomias

**Histórica, experiências até 18:** ARGUIDO, TESTEMUNHA, RELATOR, REU, UNKNOWN. Classificação de uma pessoa marcada por exemplo. ARGUIDO corresponde ao acusado criminal e REU ao réu civil. Esta taxonomia continua a reger o conjunto congelado de 50 exemplos.

**Atual, provisória para a Experiência 19:** ARGUIDO, REU, AUTOR, REQUERENTE, RECORRENTE, RECORRIDO, TESTEMUNHA, RELATOR, UNKNOWN. A fonte operacional é [config/role_taxonomy.json](../config/role_taxonomy.json).

| Papéis finos | Classe agregada derivada |
| --- | --- |
| ARGUIDO, REU | PASSIVE_PARTY |
| AUTOR, REQUERENTE | ACTIVE_PARTY |
| RECORRENTE | APPELLANT |
| RECORRIDO | APPELLEE |
| TESTEMUNHA | WITNESS |
| RELATOR | RAPPORTEUR |
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

Limite da evidência desta atualização: `venv-ner/pyvenv.cfg` não estava presente neste checkout e não foi localizado um relatório autónomo com versões/tempos desse teste funcional. Não se registam versões, VRAM ou aceleração inventadas. Confirmar a localização do ambiente usado e guardar o inventário das versões e o stdout no próximo benchmark. `requirements.txt` é uma lista de dependências do projeto, não um lockfile comprovado do ambiente GPU. A política de GPU está implementada; o novo benchmark comparável ainda está pendente.

## Próximos passos, pela ordem atual

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
