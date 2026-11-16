# Experiência 19a — auditoria agregada do pool v5 e preparação da anotação

> Enquadramento de 16-11-2026 — Auditoria histórica concluída do pool amostrado de 430 candidatos, não do inventário NER integral. As recomendações refletem a fase 19a; ver [estado atual](../docs/THESIS_STATE.md).

Data: 30-10-2026. Análise local, exclusivamente de leitura. Este relatório é o único artefacto criado: não houve nova extração, inferência NER, treino, alteração de candidatos/revisões ou adjudicação automática. Não contém pessoas, passagens, nomes de documentos-fonte ou identificadores processuais individuais.

## 1. Resultado e âmbito da verificação

**Os 430 candidatos são estruturalmente válidos, mas ainda não constituem um benchmark gold nem 430 observações independentes.** Há duplicação textual relevante e pendências de proveniência que devem anteceder os splits. É possível preparar um primeiro lote controlado de 40 candidatos de 40 grupos processuais distintos, sujeito à verificação humana indicada abaixo.

Entradas:

- `data/raw/experiment_19a_candidates_v5_gpu_full.jsonl`
- `data/raw/experiment_19a_audit_v5_gpu_full.json`

SHA-256 das entradas, respetivamente:

```text
531532bb59eeb1106c69ab8315cc7f287a25956f41d4c2ef29f8235567358eb0
69c71dcfe47a9829dc71e24ba8f1b423592d42e9fc4cead35c734ab73506dea9
```

O validador existente terminou com sucesso. A verificação suplementar confirmou:

- 430 linhas JSON válidas, IDs únicos e todos os campos obrigatórios presentes.
- Offsets locais inteiros, dentro dos limites, e `text[entity_start:entity_end] == entity` em 430/430 casos.
- Offsets documentais coerentes com os locais; alvo e contexto correspondem exatamente a fatias contínuas dos textos-fonte locais. Nenhum texto armazenado contém os markers `[ENTITY]`/`[/ENTITY]`.
- Sugestões pertencentes à taxonomia configurada. `label`, `evidence_type`, `difficulty` e `contains_distractor_role` estão a null nos 430 casos; `human_validated=false` em todos.
- Presença e consistência de `source_document_id`, `source_text_sha256`, offsets documentais, IDs candidatos e `process_provenance` com os registos documentais da auditoria. Os hashes dos 388 textos-fonte foram conferidos, e a extração de metadados foi reproduzida sem NER, sem divergências.
- As listas/contagens de grupos não resolvidos, conflitos e seleção por papel da auditoria correspondem aos metadados e ao pool.

Isto comprova integridade estrutural e rastreabilidade técnica, não a correção semântica da entidade PER, do papel, do âmbito processual ou dos próprios metadados da fonte. A concordância com o mesmo extrator de metadados não substitui adjudicação independente.

## 2. Distribuições

### Sugestões e cobertura da descoberta

As três colunas intermédias são contagens da auditoria de extração, incluindo versões com conteúdo repetido. Uma âncora próxima de PER não prova uma relação entre essa pessoa e o papel.

| Papel sugerido | Âncoras | Âncoras com PER próximo | Candidatos descobertos | Pool final |
| --- | ---: | ---: | ---: | ---: |
| ARGUIDO | 40191 | 18709 | 981 | 60 |
| REU | 296 | 78 | 26 | 10 |
| AUTOR | 1493 | 488 | 202 | 60 |
| REQUERENTE | 1512 | 179 | 153 | 60 |
| RECORRENTE | 8711 | 1523 | 504 | 60 |
| RECORRIDO | 5782 | 589 | 281 | 60 |
| TESTEMUNHA | 1782 | 1037 | 316 | 60 |
| RELATOR | 1019 | 716 | 636 | 60 |
| UNKNOWN | Não há âncora | Não aplicável | 0 | 0 |
| Total de candidatos | — | — | 3099 | 430 |

A auditoria regista 2060 candidatos após deduplicação global, antes da seleção final. Configuração registada: seed 42, máximo 60 por papel e 2 por processo/papel, contexto de 240 caracteres e quota heurística difícil de 0,25. Nenhum destes parâmetros transforma sugestões em labels finais.

### Documentos e grupos

A distribuição por ID é apresentada como histograma, sem expor IDs individuais.

| Unidade no pool | IDs distintos | Candidatos associados | 1 candidato/unidade | 2 candidatos/unidade | 3 candidatos/unidade |
| --- | ---: | ---: | ---: | ---: | ---: |
| `source_document_id` | 296 | 430 | 173 | 112 | 11 |
| `process_group_id` resolvido | 177 | 340 | 37 | 117 | 23 |

Os outros 90 candidatos têm grupo null: null não é um grupo processual único. Existem 113 candidatos sem `decision_id` resolvido, embora alguns conservem grupo resolvido. No corpus auditado completo existem 388 documentos extraídos e 178 grupos conhecidos; 149 grupos têm vários documentos, e 2 grupos têm mais de um ID exato de decisão conhecido.

A auditoria contabiliza 392 ficheiros detetados, 388 documentos extraídos com sucesso, 1 falha e 3 ficheiros ignorados. Regista 386 documentos com candidatos na descoberta; a seleção final representa 296, não 386 nem 388 documentos independentes.

### Proveniência

| `process_provenance.status` | Documentos no corpus | Documentos no pool | Candidatos |
| --- | ---: | ---: | ---: |
| `header_filename_agree` | 114 | 79 | 99 |
| `header_only` | 171 | 129 | 183 |
| `filename_only` | 23 | 22 | 35 |
| `conflict` | 44 | 30 | 48 |
| `unresolved` | 36 | 36 | 65 |
| Total | 388 | 296 | 430 |

`requires_review=true` em 274 documentos do corpus e 331 candidatos. É um sinalizador conservador: inclui proveniência de uma só fonte, não apenas conflitos. `process_number` é evidência legada, não um ID exato verificado; nunca deve substituir automaticamente `decision_id` ou `process_group_id`.

### Dificuldade e evidência

`difficulty`: null 430; easy/medium/hard 0. Evidência e distractores também ainda não estão anotados. Não é possível apresentar desempenho ou dificuldade humana por estrato.

A heurística existente sinaliza 280 contextos como potencialmente complexos: 174 têm múltiplos PER detetados e 213 múltiplos papéis lexicais, com sobreposição entre os conjuntos. Estes indicadores não são gold de dificuldade, distractores ou multi-label; servem apenas para estratificar a revisão.

## 3. Interseções das pendências de identidade

Definições: U = grupo não resolvido; C = conflito de proveniência; I = ausência de `process_number` legado. Na coluna dos candidatos, I aplica-se ao próprio registo; nas colunas documentais aplica-se aos 6 documentos listados na auditoria.

| Combinação exata, sem contar novamente outras linhas | Documentos no corpus | Documentos representados no pool | Candidatos |
| --- | ---: | ---: | ---: |
| Nenhuma destas três sinalizações | 306 | 228 | 314 |
| Só U | 33 | 33 | 58 |
| Só C | 31 | 17 | 22 |
| Só I | 2 | 2 | 3 |
| U e C, sem I | 12 | 12 | 25 |
| U e I, sem C | 3 | 3 | 7 |
| C e I, sem U | 1 | 1 | 1 |
| U, C e I | 0 | 0 | 0 |
| Total | 388 | 296 | 430 |

Consequências:

- Os 48 documentos sem grupo são 36 sem identidade obtida do cabeçalho/filename e 12 com duas raízes processuais concorrentes. Os 12 também pertencem aos 44 conflitos.
- Dos 44 conflitos, 32 conservam um grupo único apesar da discordância entre IDs exatos; os restantes 12 não têm grupo resolvido. Não concluir que todos os 32 são apenas diferenças de sufixo: a identidade exata exige revisão.
- U ou C abrange 80 documentos do corpus e 113 candidatos do pool; adicionando I, são 82 documentos e 116 candidatos. Estes totais não resultam da soma direta das três contagens iniciais.
- Os 11 candidatos sem ID legado vêm de 6 documentos: 7 também não têm grupo, mas 4 têm grupo resolvido por outra evidência. Um desses 4 é conflitante.
- Dos 48 documentos sem grupo, 31 têm um texto extraído idêntico ao de outro documento com um único grupo conhecido; isso abrange 56 dos 90 candidatos sem grupo. É uma pista para adjudicação, não autorização para preencher campos automaticamente.

Recomenda-se uma folha local de adjudicação, separada e ignorada pelo Git, conservando evidências e valores originais, decisão humana, justificação, responsável e data. Referências no corpo não devem ser promovidas à identidade da decisão-fonte.

## 4. Duplicados e fuga de informação

### Repetição observada

Os 388 documentos correspondem a **191 conteúdos textuais distintos** por `source_text_sha256`: há 188 grupos de conteúdo repetido envolvendo 385 documentos, ou 197 cópias além de uma por conteúdo. Trata-se do texto extraído, não de uma afirmação de identidade binária dos ficheiros originais. No pool há 296 documentos, mas apenas **187 conteúdos-fonte distintos**.

| Critério sobre os candidatos | Grupos/componentes | Registos envolvidos |
| --- | ---: | ---: |
| Mesma ocorrência documental, na mesma fonte e offsets | 5 | 10 |
| Mesma ocorrência e offsets em conteúdo-fonte com hash idêntico | 41 | 87 |
| Contexto marcado idêntico após normalizar espaços e capitalização | 39 | 80 |
| Mesmo alvo normalizado e similaridade do contexto marcado >= 0,92 | 43 | 89 |

Estas categorias sobrepõem-se. No primeiro critério, 3 grupos têm sugestões diferentes; isso não é automaticamente multi-label gold. Contextos diferentes da mesma ocorrência podem apresentar evidência diferente, devendo permanecer juntos nos splits e ser revistos antes de escolher representantes.

A similaridade usa `difflib.SequenceMatcher` sobre texto marcado normalizado, apenas entre alvos com grafia normalizada igual: 50 pares atingem o limiar, 49 atravessam documentos, 7 atravessam grupos conhecidos diferentes e 43 envolvem pelo menos um grupo não resolvido. Os 43 componentes são ligações por pares, não garantia de semelhança entre todos os seus membros.

Adicionalmente, Jaccard >= 0,80 de conjuntos de sequências de cinco palavras, mascarando a grafia do alvo, sinaliza 59 pares/91 registos; 56 pares atravessam fontes e 8 grupos conhecidos diferentes. Mesmo contextos exatamente iguais atravessam grupos conhecidos em 1 grupo de duplicados. Estes testes são heurísticos: texto formulaico, citações ou nomes iguais não provam identidade de pessoa/caso, nem legitimam eliminação automática.

### Regras propostas antes de qualquer split

1. Nunca dividir aleatoriamente por linha. Bloquear conjuntamente o mesmo grupo processual, documento e hash do conteúdo-fonte, mesmo quando uma versão não tenha grupo resolvido.
2. Esses vínculos estruturais já formam 186 componentes no pool: 28 de tamanho 1, 105 de tamanho 2, 25 de tamanho 3, 25 de tamanho 4, 1 de tamanho 5 e 2 de tamanho 6. Nove componentes contêm apenas grupos não resolvidos. São blocos provisórios de isolamento, não IDs adjudicados nem unidades estatísticas certificadas.
3. Adjudicar repetições entre grupos diferentes e contextos citados antes de fixar os blocos finais. A auditoria identifica 16 ligações direcionais entre grupos conhecidos através de referências no corpo, presentes em 26 documentos, dos quais 19 estão representados no pool. Uma referência não prova que o excerto do candidato cite esse caso; não fundir automaticamente toda a rede de citações.
4. Escolher representantes de repetições para anotação apenas mediante revisão dos contextos, sem apagar ou modificar o pool. Conservar um manifesto local de exclusões/agrupamentos e a razão de cada decisão.
5. Fixar uma só versão dos splits para as taxonomias fina e agregada. Agregar labels automaticamente depois da anotação fina, mantendo exatamente os mesmos exemplos e grupos.

## 5. Protocolo existente e artefactos protegidos

O [protocolo 19a](../docs/experiment_19a_annotation_protocol.md), o [revisor local](../src/annotation/review_role_candidates.py) e o [validador](../src/evaluation/validate_role_candidates_v2.py) já suportam o trabalho necessário:

- Rever uma ocorrência PER exata, sem mostrar a sugestão lexical antes da decisão; classificar só o alvo, não as pessoas vizinhas.
- Uma lista de labels finas, sem duplicados, permite multi-label apenas quando cada papel é suportado para a mesma ocorrência. UNKNOWN é exclusivo: pessoa válida sem nenhum dos oito papéis suportado. Ambiguidade entre papéis não é UNKNOWN.
- REJECT indica entidade/exemplo inutilizável; skip e uncertain não são gold. Apenas aceitação explicitamente confirmada recebe `human_validated=true`.
- Evidência explicit/implicit; UNKNOWN usa not_applicable. Uncertain fica pendente. A compatibilidade `evidence_type` é explicit/contextual/null, sem inventar uma evidência “distractor”.
- Dificuldade e papéis distractores são avaliados pelo humano. Registar âmbito por label: processo atual, citado, ambos ou unclear. Um papel de processo citado é elegível para a tarefa mention-level, mas não estabelece um papel no caso atual.
- Preservar texto, offsets e metadados; guardar revisões num novo ficheiro local ignorado. O revisor suporta resume e prevenção de IDs duplicados no seu próprio ficheiro, não deduplicação semântica entre pools diferentes.

O benchmark histórico permanece com 50 exemplos, 10 por classe histórica, todos validados. O SHA-256 continua a ser `f687174287e7aeb50283a42e510897eb4bd9daa663749b3f3a4507c77a3bd6c8`. Não foi usado como seed nem como demonstração; a consulta foi apenas para auditoria de sobreposição. Não se encontrou sobreposição dos grupos normalizáveis, referências detetadas a esses grupos ou contenção exata de contextos marcados normalizados com pelo menos cinco palavras. Contudo, 3 IDs históricos não são interpretados pelo normalizador atual; as verificações lexicais não excluem paráfrases, aliases ou relações não detetadas. Não certificar ausência absoluta de leakage.

O piloto v4 conserva 61 candidatos de 10 documentos e 10 revisões em 10 documentos: 10 aceites, 0 rejeitados, 2 multi-label, 12 atribuições (ARGUIDO 4, RECORRENTE 4, TESTEMUNHA 1, RELATOR 2, UNKNOWN 1). Dez candidatos revistos não significam dez acórdãos integralmente anotados.

No pool v5 existem 10 candidatos de 7 documentos do piloto e 17 candidatos dos 9 grupos piloto conhecidos. Só 1 das 10 ocorrências já revistas está selecionada novamente com os mesmos campos-fonte e ID. Não copiar as revisões por semelhança de nome, nem presumir que novos campos de âmbito/proveniência foram retroativamente validados. Conservar o piloto como estudo separado; excluir as suas fontes, hashes e grupos conhecidos do próximo lote independente. O hash do input faz parte do resume: não reutilizar o ficheiro de revisão v4 como saída/resume de v5.

## 6. REU e UNKNOWN: recolha controlada, sem gold automático

**REU:** é a âncora menos frequente, presente em 63 documentos do corpus; 218 das 296 ocorrências não têm PER próximo segundo a configuração. Das 78 restantes resultam 26 candidatos descobertos e 10 selecionados, provenientes de 8 documentos/6 grupos conhecidos, com 1 candidato sem grupo. Os 26 descobertos não são necessariamente 26 pessoas ou contextos independentes. A auditoria não discrimina todas as perdas pós-deduplicação/seleção por papel; não atribuir a redução 26 -> 10 exclusivamente ao NER ou às quotas.

Entre os 10 contextos selecionados, 7 contêm vocabulário penal e 3 vocabulário civil numa pesquisa lexical simples, com conjuntos potencialmente sobrepostos. É um alerta para revisão, não diagnóstico do tipo de processo. REU gold exige réu civil; o uso histórico de “réu” em matéria penal, citações, pessoas coletivas e âncoras sem relação com o alvo podem não produzir REU. As cópias textuais também inflacionam a cobertura aparente.

Próxima recolha, apenas se autorizada após revisão deste pool: selecionar decisões civis por metadados verificados, procurar as variantes já suportadas e construções processuais pertinentes, inspecionar localmente uma amostra de âncoras sem PER para distinguir distância, correferência e omissão NER. Alvos continuam a exigir spans PER exatos do modelo ou um procedimento humano separado e documentado; não voltar ao fallback de capitalização nem preencher quotas por relabeling automático. Reservar novos processos e preservar contagens antes/depois de cada filtro.

**UNKNOWN:** a ausência é esperada numa descoberta guiada por oito papéis, não prova de inexistência de pessoas fora da taxonomia. A revisão pode produzir UNKNOWN quando a âncora se referir a outra pessoa ou o alvo tiver apenas papel fora do âmbito; o piloto já demonstrou essa possibilidade. Não converter candidatos ambíguos, rejeitados ou sem processo em UNKNOWN.

Para cobertura posterior, recolher uma amostra PER independente de âncoras-alvo, em processos reservados, e um estrato controlado de papéis fora do âmbito, mantendo sugestões como hipóteses de descoberta, nunca gold. A definição desse novo estrato/representação exige tarefa separada; não inventar exemplos UNKNOWN neste pool. Autores de obras/artigos citados exigem atenção especial: CITATION_AUTHOR é requisito pendente de 30-10-2026, não label implementada, nem AUTOR processual. Reservar os casos para adjudicação metodológica; não recodificar UNKNOWN nem sugerir preservação automática de identidades. Taxonomia e política de anonimização dependem dos orientadores e do STJ.

## 7. Proposta concreta para o próximo lote

**Lote proposto: 40 ocorrências, de 40 grupos distintos, cinco por cada uma das oito sugestões existentes.** É uma quota de descoberta, não garantia de cinco labels finais por classe. UNKNOWN e multi-label emergem da decisão humana, sem quotas gold impostas a priori.

Condições verificadas de disponibilidade, após excluir fontes, hashes e grupos conhecidos do piloto e grupos históricos normalizáveis:

| Sugestão | Candidatos disponíveis | Grupos distintos disponíveis | Critério de proveniência |
| --- | ---: | ---: | --- |
| ARGUIDO | 16 | 16 | Cabeçalho e filename concordantes |
| REU | 8 | 5 | 2 concordantes; 6 apenas cabeçalho |
| AUTOR | 7 | 7 | Concordantes |
| REQUERENTE | 12 | 11 | Concordantes |
| RECORRENTE | 12 | 12 | Concordantes |
| RECORRIDO | 13 | 13 | Concordantes |
| TESTEMUNHA | 19 | 19 | Concordantes |
| RELATOR | 13 | 13 | Concordantes |

Uma correspondência bipartida entre quotas e grupos confirmou a viabilidade de 40 grupos diferentes; nenhum manifesto ou subset foi escrito. Para REU, a lista admissível exclui `filename_only`, conflito e grupo null. A escolha final deve rever manualmente a identidade dos casos apenas com cabeçalho antes de os admitir como gold; concordância entre duas fontes também não garante correção material.

Procedimento recomendado:

1. Preparar, numa tarefa posterior autorizada, um manifesto local de IDs existentes, exclusões, blocos de duplicados e seed 42. Não voltar a extrair nem modificar candidatos. O seletor padrão do revisor não aplica sozinho todos estes filtros de proveniência, exclusão de pilotos e duplicados; não apresentar uma chamada simples com `--pilot-size 40` como cumprimento deste desenho.
2. Escolher primeiro cinco grupos REU e depois completar os restantes papéis sem repetir grupos. Dentro das escolhas admissíveis, procurar cerca de 25% de contextos com indicadores de complexidade, sem transformar o indicador em `difficulty=hard`; se não for possível, registar a proporção efetiva.
3. Rever cegamente quanto à sugestão, verificar pessoa única/offsets e papel por contexto, marcar âmbito por label, evidência, dificuldade, distractores e notas privadas. Não forçar aceitação para preencher quotas. Se uma pendência de identidade inviabilizar uma vaga rara, reduzir/adiar a vaga em vez de fabricar um exemplo.
4. Fazer segunda anotação independente dos cinco REU propostos e de cinco outros casos pré-selecionados (25% do lote), distribuídos por papéis/complexidade; adjudicar desacordos. Casos adicionais incertos podem ser enviados separadamente a adjudicação, sem contaminar a estimativa de concordância do subconjunto pré-selecionado.
5. Guardar nova revisão e adjudicações em `data/raw/`, sem sobrescrever v4/v5. Publicar apenas resumo agregado: aceites, rejeitados, adiados/incertos, pessoas/menções, incidências por label, multi-label, âmbitos, evidência, dificuldade, distractores e cobertura processual. Medir concordância apenas onde houver dupla anotação efetiva.
6. Depois deste lote, decidir recolha suplementar REU/UNKNOWN segundo lacunas humanas, visando cerca de 10–12 exemplos confirmados por papel fino. Em multi-label, contagens por papel sobrepõem-se e não devem ser confundidas com número de registos. Só depois consolidar benchmark e splits; ainda não existem resultados de modelos para a comparação fina/agregada.

## 8. Limitações e preservação

O corpus, os filtros PER e a descoberta por âncoras introduzem viés; os resultados não estimam recall de pessoas, prevalência de papéis ou qualidade de anonimização ponta a ponta. Duplicados, texto formulaico e citações reduzem a independência das observações. Identificadores e heurísticas textuais podem falhar; o limiar de similaridade não foi validado por humanos nesta análise. As quotas propostas privilegiam proveniência limpa e, por isso, não são uma amostra representativa do corpus.

O nome `gpu_full` não substitui um log de dispositivo: não foi executado benchmark GPU nesta tarefa. O relatório não modifica o estado histórico de outras notas, que podem anteceder esta extração.

Permanecem intactos pool e auditoria v5, candidatos e revisões v4, benchmark de 50 exemplos, scripts, modelos e resultados anteriores. Não houve chamadas externas, commits ou publicação de dados privados. A verificação executada foi de dados/metadados e leitura de código; não se executou novamente NER nem a suite de modelos/testes como se houvesse alterações de implementação.

Fontes de implementação/metodologia: [extrator](../src/data/extract_role_candidates_v2.py), [proveniência](../src/data/role_provenance.py), [validador](../src/evaluation/validate_role_candidates_v2.py), [revisor](../src/annotation/review_role_candidates.py), [taxonomia](../config/role_taxonomy.json), [protocolo](../docs/experiment_19a_annotation_protocol.md), [decisões](../docs/DECISIONS.md) e [estado anterior](../docs/THESIS_STATE.md). Dados de controlo locais consultados apenas para agregados/sobreposição: pool e revisões v4 indicados acima e o benchmark congelado. Nenhum dos seus conteúdos sensíveis é reproduzido aqui.
