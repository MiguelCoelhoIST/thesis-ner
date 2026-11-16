# Experiência 19a — primeiro lote de anotação humana

> Enquadramento de 16-11-2026 — Preparação histórica concluída do lote de 40, sem anotação gold. Quotas, recomendações humanas e CITATION_AUTHOR registam aquela fase; não limitam o universo atual. Ver [estado atual](../docs/THESIS_STATE.md).

Preparado em 30-10-2026. Seleção local de candidatos existentes, sem nova extração, NER, classificação automática ou treino. Este relatório contém apenas agregados; os registos, IDs, evidências e decisões individuais de seleção permanecem em ficheiros ignorados pelo Git.

## Resultado

**40 candidatos, cinco por cada um dos oito papéis sugeridos, de 40 grupos processuais e 40 conteúdos-fonte distintos.** As quotas foram atingidas sem admitir candidatos com identidade própria conflitante/não resolvida ou componentes com raízes processuais concorrentes. Não foram atribuídas labels gold.

| Sugestão lexical | Elegíveis após os filtros | Selecionados |
| --- | ---: | ---: |
| ARGUIDO | 16 | 5 |
| REU | 8 | 5 |
| AUTOR | 6 | 5 |
| REQUERENTE | 12 | 5 |
| RECORRENTE | 12 | 5 |
| RECORRIDO | 13 | 5 |
| TESTEMUNHA | 19 | 5 |
| RELATOR | 12 | 5 |
| UNKNOWN | 0 | 0 |
| Total | 98 | 40 |

São quotas de descoberta, não equilíbrio de classes humanas. O anotador pode aceitar outro papel, vários papéis, UNKNOWN, rejeitar ou adiar o candidato.

## Artefactos e reprodução

- Lote privado: `data/raw/experiment_19a_annotation_batch01_v1.jsonl`.
- Manifesto privado: `data/raw/experiment_19a_annotation_batch01_v1_manifest.json`.
- Seletor novo: [prepare_role_annotation_batch.py](../src/annotation/prepare_role_annotation_batch.py).
- Testes novos, exclusivamente sintéticos: [test_prepare_role_annotation_batch.py](../tests/test_prepare_role_annotation_batch.py).
- Revisor reutilizado, **sem alterações**: [review_role_candidates.py](../src/annotation/review_role_candidates.py).

Seed: **42**; quota máxima: **5 por sugestão**, sem preenchimento obrigatório; algoritmo `19a-batch-v1`. O manifesto guarda caminhos e hashes dos cinco inputs, hash do seletor, IDs selecionados em ordem, motivos de exclusão por registo, raízes de bloqueio, estados dos aliases, indicadores de contexto e resumo agregado.

SHA-256 do lote:

```text
6a392e6c2215f2faaa4ceee30ec8da0085016e2291a3f9043c8704404d998b05
```

Os 40 registos mantêm todos os valores originais do pool v5, incluindo IDs, texto, offsets e proveniência. `label=null`, `human_validated=false`; evidência, dificuldade e distractores continuam a null em todos. Não se iniciou a revisão nem se criou um ficheiro de decisões humanas vazio.

## Critérios e exclusões

Foram consultados AGENTS.md, THESIS_STATE.md, DECISIONS.md, o [protocolo mention-level](../docs/experiment_19a_annotation_protocol.md) e a [auditoria agregada v5](experiment_19a_v5_gpu_full_annotation_audit.md). Inputs privados/controlo:

- Pool e auditoria `experiment_19a_candidates_v5_gpu_full.jsonl` / `experiment_19a_audit_v5_gpu_full.json`.
- Pool piloto `experiment_19a_candidates_v4_smoke10.jsonl` e as dez revisões `experiment_19a_v4_smoke10_reviews.jsonl`.
- Benchmark congelado `data/eval/roles_eval_real_candidates_v1.jsonl`, consultado apenas para exclusão, nunca como seed, treino ou demonstração.

O seletor constrói componentes conservadores de bloqueio utilizando **todos os documentos da auditoria**, incluindo versões que não foram selecionadas para o pool. Liga identidade documental, hashes textuais e raízes potenciais de cabeçalho/filename/IDs candidatos. O ID legado também é uma aresta de precaução, nunca uma identidade verificada. Aliases com evidência concorrente não desaparecem quando a sua própria candidatura é excluída.

São acrescentadas ligações de conteúdo entre candidatos e contra os conjuntos protegidos:

1. Contenção de contexto normalizado, com pelo menos cinco palavras em ambos os contextos.
2. Mesma grafia normalizada do alvo e similaridade `SequenceMatcher` do contexto marcado >= 0,92.
3. Jaccard >= 0,80 de sequências de cinco palavras, mascarando o alvo.

Estes testes são bloqueios conservadores, não adjudicação de identidade, papéis ou duplicados. Foram registados 67 pares de ligação dentro do pool e 27 contra registos protegidos. As relações propagam-se pelos componentes. Uma referência no corpo não é promovida a ID da decisão-fonte, nem se funde automaticamente toda a rede de citações.

Filtros de admissão:

- Nenhuma ligação ao piloto protegido — foi reservado o pool dos dez documentos piloto, não apenas as dez ocorrências revistas — ou ao benchmark pelos identificadores/conteúdos disponíveis.
- Uma só raiz processual potencial no componente de bloqueio; ID exato e grupo próprios resolvidos.
- Preferência por `header_filename_agree`. A única exceção é REU com `header_only`, sem contradição detetada no componente, devido à escassez. `filename_only`, `conflict` e `unresolved` próprios não são admitidos.
- Registos ainda não anotados. Um único candidato por componente conservador, evitando repetição de conteúdo, fonte ou grupo, mesmo que aliases tenham IDs distintos.

A seleção usa correspondência bipartida entre vagas por papel e componentes, procurando o máximo admissível sem exceder cinco por papel. As preferências por vaga alternam contextos menos complexos, múltiplos PER, múltiplas âncoras, referência a outro processo e o indicador de frase única; os desempates são hashes determinísticos de seed/vaga/ID. Não é uma amostragem uniforme nem uma otimização global da dificuldade.

Dos 430 registos, **332 foram excluídos por pelo menos um filtro**; outros **58 eram elegíveis mas não foram selecionados** por quota ou componente partilhado. Motivos sobrepostos, que não se devem somar:

| Motivo | Candidatos |
| --- | ---: |
| Proveniência própria fora dos critérios admitidos | 325 |
| Falta de ID exato/grupo próprio resolvido | 113 |
| Componente sem raiz única ou com raízes concorrentes | 83 |
| Ligação documental/processual/de conteúdo a conjuntos protegidos | 26 |

Na entrada havia 48 candidatos com estado `conflict`, 90 sem grupo e 11 sem ID legado, conforme a auditoria anterior; estes conjuntos não são disjuntos. No lote: **zero conflitos próprios, zero avisos de conflito em aliases, zero IDs exatos/grupos em falta e zero IDs legados em falta**. Não se resolveu nem sobrescreveu qualquer discrepância.

## Proveniência e diversidade do lote

| Indicador | Candidatos |
| --- | ---: |
| Cabeçalho e filename concordantes | 37 |
| Apenas cabeçalho, todos REU | 3 |
| Múltiplos PER no contexto segundo os metadados NER | 16 |
| Vários papéis lexicais no contexto | 24 |
| Ambos os indicadores anteriores | 14 |
| Referência a outro grupo processual no contexto | 8 |
| Múltiplos PER e contexto de uma frase, por aproximação | 1 |
| Pelo menos um dos indicadores de complexidade | 29 |
| Sem esses indicadores | 11 |

Os indicadores sobrepõem-se. Os oito casos com referências não apontam para outro grupo-fonte selecionado neste lote, segundo o parser disponível. Isto não prova que a pessoa-alvo participe no processo citado.

Os **três REU apenas com cabeçalho exigem confirmação humana da proveniência antes de inclusão gold**, não apenas confirmação do papel. O manifesto permite localizá-los sem expor os IDs no relatório. O revisor já mostra o estado e o aviso de identidade. Registar a adjudicação num artefacto privado separado; se não for possível confirmar, adiar/rejeitar conforme a natureza do problema, sem forçar substituições ou quotas gold.

`context_per_count` não fornece todos os spans vizinhos e a segmentação por pontuação é aproximada, especialmente com abreviaturas jurídicas. O caso de frase única é um proxy: verificar manualmente se existem realmente várias pessoas na mesma frase. Múltiplas âncoras não significam múltiplos papéis do alvo. A dificuldade final e os distractores só serão definidos pelo anotador.

## Validações executadas

- Validador de candidatos: **40 registos, sucesso**, cinco por cada sugestão suportada e zero UNKNOWN sugeridos.
- Todos os registos selecionados são iguais aos originais, com offsets exatos e campos de anotação por preencher.
- Uma segunda seleção em memória com os mesmos inputs/seed reproduziu **os mesmos 40 IDs e a mesma ordem**; não escreveu outro lote.
- Os guards de conteúdo não encontraram ligações entre os 40 selecionados, nem destes aos registos protegidos. Hashes e grupos são todos distintos; o matching assegura componentes distintos.
- A seleção interna do revisor com `--pilot-size 40 --seed 42` inclui todos os 40; poderá mudar a ordem de apresentação, não a composição.
- **72 testes passaram**, incluindo seis novos de seleção determinística/compatibilidade, bloqueio por alias conflitante, propagação de proteção, quotas não forçadas, duplicação e comparação com gold sem metadados documentais.
- Hashes dos cinco inputs confirmados inalterados, incluindo as dez revisões e o gold50. Hash do seletor e do output conferidos com o manifesto. Lote e manifesto foram verificados como ignorados pelo Git.

## Iniciar e retomar a revisão

Executar na raiz do repositório. O Python abaixo foi o usado na preparação e nos testes; não é necessário carregar o modelo NER/GPU para anotar.

```powershell
.\venv\Scripts\python.exe src/annotation/review_role_candidates.py `
    --input data/raw/experiment_19a_annotation_batch01_v1.jsonl `
    --output data/raw/experiment_19a_annotation_batch01_v1_reviews.jsonl `
    --pilot-size 40 --seed 42
```

Para retomar, repetir **os mesmos argumentos** e acrescentar `--resume`. Não reutilizar a saída v4 nem alterar o lote depois de iniciar a revisão. O revisor guarda cada decisão e distingue UNKNOWN, REJECT, skip e uncertain. Apenas aceitação explicitamente confirmada pode validar um registo. A tarefa é mention-level: registar âmbito por label, incluindo papéis de processos citados; estes não provam papéis no caso atual.

Validação posterior das revisões:

```powershell
.\venv\Scripts\python.exe src/evaluation/validate_role_candidates_v2.py `
    data/raw/experiment_19a_annotation_batch01_v1_reviews.jsonl
```

Para reproduzir a preparação, usar o comando seguinte com **novos nomes de saída**; o seletor recusa sobrescrita. Não é necessário voltar a executá-lo para iniciar a revisão:

```powershell
.\venv\Scripts\python.exe src/annotation/prepare_role_annotation_batch.py `
    --pool data/raw/experiment_19a_candidates_v5_gpu_full.jsonl `
    --audit data/raw/experiment_19a_audit_v5_gpu_full.json `
    --pilot data/raw/experiment_19a_candidates_v4_smoke10.jsonl `
    --reviews data/raw/experiment_19a_v4_smoke10_reviews.jsonl `
    --gold data/eval/roles_eval_real_candidates_v1.jsonl `
    --output data/raw/experiment_19a_annotation_batch01_v1_reproduction.jsonl `
    --manifest data/raw/experiment_19a_annotation_batch01_v1_reproduction_manifest.json `
    --seed 42 --per-role 5
```

## UNKNOWN e limitações

**A lacuna UNKNOWN mantém-se.** A descoberta por âncoras dos oito papéis não é uma amostra de negativos. Este lote pode originar UNKNOWN por decisão humana, mas não garante cobertura suficiente. UNKNOWN é pessoa válida sem papel-alvo suportado; não é rejeição, conflito de proveniência ou ambiguidade entre papéis.

Propõe-se, numa recolha futura autorizada, um lote separado de cerca de 20–30 menções PER reais, de novos grupos reservados: uma parte amostrada sem condicionamento a âncoras dos oito papéis e outra estratificada por contextos potencialmente fora do âmbito. Conservar offsets/proveniência, aplicar os mesmos bloqueios e revisão cega, sem atribuir previamente UNKNOWN. Reportar os dois estratos separadamente e aceitar o papel que o humano efetivamente encontrar; isto não estima prevalência populacional. A meta posterior de 10–12 exemplos humanos por papel não autoriza fabricar negativos.

Autores de obras/artigos citados requerem a decisão pendente CITATION_AUTHOR, ainda não implementada. Não os tratar automaticamente como AUTOR processual, não recodificar UNKNOWN nem preservar identidades automaticamente; a taxonomia/política exigem validação dos orientadores e do STJ.

Os guards são heurísticos e podem bloquear texto formulaico sem verdadeira identidade ou falhar paráfrases. Três IDs históricos do gold não são interpretados pelo normalizador: a comparação por conteúdo mitiga, mas não elimina essa limitação. Não se certifica independência absoluta nem se criaram splits. Uma amostra condicionada a proveniência limpa/âncoras não mede recall NER ou generalização do classificador. A revisão deve confirmar pessoa única, contexto, papéis e proveniência, sem assumir que o nome do ficheiro ou a sugestão são verdade.

Não houve mudanças em datasets existentes, gold50, revisões piloto, scripts existentes, modelos ou resultados anteriores. Foram acrescentados apenas seletor/testes, este relatório e os dois outputs privados. Sem APIs externas, treino, início automático da revisão ou commit.
