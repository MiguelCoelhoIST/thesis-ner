# Decisões metodológicas e operacionais

Atualizado em **16-11-2026**. Este registo consolida decisões já presentes no código/protocolos e requisitos posteriores. Não atribui datas históricas que não estejam comprovadas e não substitui a validação pelos orientadores e pelo STJ. D15–D24 conservam a evolução histórica; D25 e o topo de [THESIS_STATE.md](THESIS_STATE.md) indicam a etapa mais recente.

| ID | Decisão | Estado / fundamento |
| --- | --- | --- |
| D01 | Arquitetura Text -> Eduardo NER -> PER -> classificador de papéis. Manter a deteção de entidades separada da classificação de papéis. | Em uso. [Pipeline](../src/evaluation/pipeline_roles.py), [extrator](../src/data/extract_role_candidates_v2.py). |
| D02 | Preservar as cinco classes históricas e os 50 exemplos reais congelados, sem treino, seeds ou demonstrações com esse conjunto. | Em vigor. Hash e resultados em [THESIS_STATE.md](THESIS_STATE.md); [Experiência 16](../results/experiment_16_real_stj_evaluation_v1.txt). |
| D03 | Conservar a taxonomia histórica de nove papéis da Experiência 19 e derivar agregadas automaticamente, com os mesmos exemplos/splits. | Comparação ainda sem resultados. [Configuração histórica](../config/role_taxonomy.json); taxonomia operacional v2 de dez classes em D20 e [role_taxonomy_v2.json](../config/role_taxonomy_v2.json). |
| D04 | Extrair alvos apenas de spans PER do modelo Eduardo; âncoras lexicais sugerem papéis mas não provam nem entidade nem label. Não usar fallback regex nem inventar divisões de nomes. | Implementado após falhas do piloto heurístico. Auditoria e revisão humana continuam obrigatórias. [Extrator](../src/data/extract_role_candidates_v2.py). |
| D05 | Preservar texto contínuo e offsets exatos; markers são derivados para inferência. Manter IDs, proveniência e outputs versionados. | Em vigor. [Utility](../src/utils/entity_marking.py), [protocolo](experiment_19a_annotation_protocol.md). |
| D06 | A anotação nova é mention-level e pode ser multi-label. Um papel de um processo citado é elegível se suportado, com âmbito registado por label; não implica papel no caso atual. | Implementado no revisor/protocolo. Experiências current-case exigem outra filtragem/adjudicação. [Protocolo](experiment_19a_annotation_protocol.md), [revisor](../src/annotation/review_role_candidates.py). |
| D07 | UNKNOWN é uma pessoa válida sem papel-alvo suportado; REJECT é exemplo/entidade/span inutilizável. Incerteza de label não se converte em UNKNOWN. Apenas confirmação humana explícita valida anotações aceites. | Em vigor. Evidência explicit/implicit, not_applicable para UNKNOWN e uncertain para pendências. [Validador](../src/evaluation/validate_role_candidates_v2.py). |
| D08 | Conservar separadamente o ID exato da decisão e o grupo processual normalizado. Agrupar decisões relacionadas e incidentes no mesmo split; não escolher silenciosamente entre cabeçalho e filename. | Implementado; há conflitos ainda por adjudicar. [Auditor de metadados](../src/data/role_provenance.py), [relatório](../results/experiment_19a_provenance_report.txt). |
| D09 | AUTOR designa o demandante civil, não o autor de um crime ou obra. REU é civil, ARGUIDO criminal. Rever a lacuna de cobertura REU do piloto, sem fabricar dados. | Critério atual; linguagem ambígua exige contexto e revisão. [Protocolo](experiment_19a_annotation_protocol.md). |
| D10 | Diagnósticos multi-entidade ficam separados das métricas dos 50 exemplos; pilotos pequenos não são avaliações estatísticas finais. | Em vigor. [Resultados 16](../results/experiment_16_real_stj_predictions_v1.json), [diagnóstico Qwen](../results/qwen3_8b_multi_entity_diagnostic_v1.json). |
| D11 | Usar `venv-ner` dedicado para NER/GPU; GPU é opt-in, exigida antes do carregamento. Validar execução limitada antes da extração completa. | Teste funcional confirmado em 30-10-2026; NER integral do job 15216 confirmado pelo utilizador em 16-11-2026 (D21). Os [testes com mocks](../tests/test_role_candidate_device.py) não validam hardware real. |
| D12 | O segmentador de Martim será avaliado separadamente após o baseline de taxonomia. | Planeado; não marcado como integrado/avaliado. [Plano 19](../results/experiment_19_plan.txt). |
| D13 | Dados pessoais, documentos brutos, modelos, checkpoints e ambientes nunca entram no Git. Não fazer commits/publicação automaticamente. | Regra permanente do projeto e desta tarefa. [AGENTS.md](../AGENTS.md), [.gitignore](../.gitignore). |
| D14 | Distinguir autores de obras/artigos citados, inicialmente designados CITATION_AUTHOR, de AUTOR processual. | Requisito inicial de 30-10-2026; nome não adotado. REFERENCE autorizada na taxonomia v2 em D20; política de preservação pendente. |

## D14: âmbito e questões pendentes

Registo histórico do requisito inicial, superado quanto ao nome/representação por D20. REFERENCE está implementada na configuração/tarefa v2; não existem por isso novas labels gold nem autorização de preservar nomes. As questões institucionais seguintes mantêm-se.

`CITATION_AUTHOR` distingue autoria bibliográfica/citada de AUTOR processual e de UNKNOWN. A designação é provisória; não altera a configuração atual nem legitima a migração automática de labels históricas.

Antes de implementar, validar com orientadores e STJ:

1. Se será papel, atributo independente ou outra camada, e como coexiste com papéis processuais/multi-label.
2. Que evidência distingue autoria de obra/artigo, mera menção, autoria de um facto/crime e participação processual.
3. Como anotar nomes ambíguos, citações incompletas, âmbito e incerteza, sem assumir identidade entre menções.
4. Em que condições o sistema pode sugerir preservação de um nome e como essa sugestão é revista por humanos. Não há autorização para exclusão automática da anonimização.
5. Que dados, métricas, splits e critérios de erro serão usados na avaliação dessa capacidade e da sua interação com a anonimização.

A partir de D20 existe label/mapeamento REFERENCE solicitado pelo utilizador. A categoria não foi medida pela extração NER nem se tornou gold automaticamente. As regras de preservação de identidades e a validação científica/institucional da taxonomia final continuam pendentes.

## Evidência, conflitos e atualização

- Para resultados, usar o artefacto específico e o seu dataset/protocolo. Para 19b/19c usar `config/role_taxonomy_v2.json`, dez labels incluindo REFERENCE; preservar `config/role_taxonomy.json` para reprodução histórica. CITATION_AUTHOR não é uma label adotada.
- README e notas antigas podem descrever versões anteriores. Não apagar essa história nem promover uma conclusão antiga a resultado global; explicitar a versão relevante em [THESIS_STATE.md](THESIS_STATE.md).
- A confirmação do teste funcional GPU é informação do utilizador; os logs/versionamentos desse ambiente deverão ser preservados localmente no próximo benchmark. Não inferir tempo de execução nem versões instaladas a partir dessa confirmação.
- As dez revisões v4 permanecem como anotadas. Campos de âmbito/evidência/proveniência acrescentados posteriormente não são retroativamente considerados validados.
- Uma adjudicação posterior deve citar a evidência, conservar o valor original e criar uma versão/artefacto separado. Não sobrescrever datasets ou resultados antigos.
- Não incluir neste registo pessoas ou excertos dos acórdãos. Documentar decisões com métricas, contagens e referências seguras a ficheiros.

## D15 — Experiência 19b: assistência LLM e SILVER (30-10-2026)

Por pedido do utilizador, preparar propostas zero-shot com Qwen3-8B para o lote 19a de 40 candidatos, sem exigir anotação manual integral a um anotador sem formação jurídica. São propostas SILVER, nunca gold nem human-validated; não enviar sugestões lexicais ao modelo e não usar APIs externas. Preservar a necessidade de adjudicação jurídica independente para alegações de correção.

REFERENCE é uma categoria experimental de autoria bibliográfica nesta experiência, separada dos nove papéis finos. Esta autorização não acrescenta uma label ao mapper/configuração, não resolve a taxonomia final CITATION_AUTHOR e não autoriza exclusões automáticas de anonimização. O gold50 e revisões piloto não são dados de prompting ou treino. Ver [protocolo e execução 19b](experiment_19b_silver_annotation.md). Implementação/testes concluídos; smoke real bloqueado localmente por CUDA indisponível, sem pesos Qwen completos em cache; execução INESC não submetida.

## D16 — Separação das estratégias e autorização de recursos (30-10-2026)

Orientação posterior: distinguir anotação assistida com GPT/Claude (procedimento do professor Borbinha ainda por documentar) de Qwen local para experiências de classificação. A implementação 19b fica preparada, sem decidir antecipadamente que Qwen será o anotador. Não instalar modelos, descarregar pesos, enviar textos privados a APIs ou submeter jobs até confirmação específica. Ausência de formação jurídica não converte saídas LLM em gold independente.

O acesso INESC e `venv-ner` CUDA foram confirmados pelo utilizador; a tentativa desta sessão não chegou ao servidor por falha DNS. Só se autorizou inspeção remota de leitura. Execução GPU exige verificar Slurm e recursos; manter o mapeamento CUDA do scheduler, não reutilizar automaticamente a GPU física 3 de uma execução anterior. Comandos de preflight e limitações em [19b](experiment_19b_silver_annotation.md).

## D17 — Piloto externo desidentificado; Qwen suspenso (30-10-2026)

Priorizar a preparação local dos cinco primeiros candidatos para futura anotação ChatGPT/Claude. Qwen fica temporariamente suspenso, sem jobs/downloads, até nova direção. A autorização atual cobre exportação local e inspeção pelo utilizador, **não envio externo**.

Pseudonimizar pessoas e outros identificadores, manter IDs originais e edições reversíveis apenas num mapa privado ignorado e exportar IDs opacos, sem suggested_label. Uma transformação reversível/NER/regex não certifica anonimização; todos os exemplos precisam de inspeção de privacidade/contexto antes da eventual partilha. Respostas externas são propostas SILVER, nunca human-validated automaticamente. Ver [exportação e limitações](external_annotation_export.md).

## D18 — Universo completo de documentos/menções, sem quotas (30-10-2026)

Nova orientação: preparar anotação das menções PER de todos os conteúdos únicos do corpus, não limitar aos 40/430 exemplos históricos. Deduplicar documentos por hash, conservar aliases e blocos conservadores de processos relacionados, manter ocorrências/contextos distintos da mesma pessoa. Âncoras deixam de definir a cobertura; não fornecer suggested_label ao anotador. Os outputs de anotação continuarão SILVER, nunca gold automático, incluindo REFERENCE experimental e multi-label sustentado.

A auditoria antiga não contém todas as previsões e cobre apenas parte do texto. Foi feito planeamento local com 191 textos, 187 blocos conservadores e 384 ocorrências recuperadas; o total completo permanece desconhecido até uma passagem NER de cobertura integral. Há callback opcional de persistência e comando preparado, mas não foi executado NER completo nem transmitidos dados. Preparação privada, verificação de privacidade e autorização de envio são fases distintas. Ver [dimensão e ficheiros](../results/experiment_19b_corpus_plan02.md). Qwen continua suspenso; benchmarks e revisões preservados.

## D19 — Recuperação auditável e lotes sem falsa completude (11-11-2026)

Reutilizar spans NER guardados somente após validar texto-fonte e offsets. Mesma ocorrência não é contada novamente; variantes sobrepostas ficam em revisão sem inventar identidades/offsets. O inventário recuperado chegou a 412 ocorrências, mas continua parcial, não uma substituição do universo de 191 textos. Todas as ocorrências e contextos diferentes permanecem elegíveis para inventário integral, independentemente de âncoras e sem quotas por papel.

Planeamento em lotes não amostra dados nem define splits: todas as menções disponíveis são incluídas, com reservas gold/piloto e casos de identidade incerta separados. Material privado não está autorizado para transmissão; respostas futuras serão SILVER. O planeador recusa inventários parciais por omissão e não cria textos prontos para enviar. Não substituir a passagem NER necessária por estimativas de dimensão ou interpretar consenso LLM como gold. [Relatório da retoma](../results/experiment_19b_corpus_inventory_20261111.md).

## D20 — Execução NER e taxonomia principal v2 (11-11-2026)

Orientação de 11-11-2026: smoke de três documentos seguido dos 191 conteúdos únicos, via acesso INESC/g09 e venv-ner, sem novos inventários recuperados/amostras. Aquela revisão preparou o wrapper, sem submeter jobs. Execução integral posteriormente confirmada em D21; o [guia de execução NER](experiment_19b_ner_execution.md) foi consolidado, distinguindo acesso SSH de nó Slurm e referências privadas opcionais, e não é uma ordem para repetir a extração.

REFERENCE passa à taxonomia principal solicitada de dez classes em `config/role_taxonomy_v2.json`; a configuração histórica de nove fica preservada. Conservar labels específicas/múltiplas e respostas originais; derivar agrupadas automaticamente sobre os mesmos exemplos/splits. REFERENCE fica separada na agregação, sem fusão adicional presumida. `other_roles` preserva designação/evidência/âmbito de papéis fora da lista, sem os promover silenciosamente a classes. SILVER nunca é human-validated automaticamente e a categoria REFERENCE não autoriza preservação de identidades.

## D21 — NER integral concluído e evidência remota (16-11-2026)

O utilizador confirmou o job Slurm **15216, COMPLETED, ExitCode 0:0**: 388 documentos auditados, 191 textos distintos, 191/191 processados, 24.467 ocorrências PER aceites, 24.977 previsões PER brutas, `inventory_complete=True`, `NER_executed=True`, `LLM_calls=0`. Adotar estas contagens no estado atual, atribuindo explicitamente a fonte ao utilizador. Não confundir spans previstos com pessoas únicas, labels jurídicas, qualidade NER ou resultados da comparação fina/agregada.

Os relatórios dos jobs 15209, 15215 e 15216 estão apenas no g09 e serão analisados separadamente; não foram inspecionados nesta consolidação. Não inventar conteúdos, duração, rejeições ou configurações desses relatórios. Preservar outputs e manifestos privados; não concatenar parciais de jobs anteriores nem repetir NER para preparar anotação.

O commit `fc069e15bac5d1638848efa3e2d782de23b86f56` protege o limite físico do BERT sem truncagem: valida WordPieces com tokens especiais, subdivide janelas excessivas e conserva offsets, sobreposição e previsões. Não alterar a pipeline que concluiu o corpus numa revisão documental.

## D22 — Prioridade 19c: anotação assistida e separação de papéis (16-11-2026)

Dar prioridade à preparação de anotação GPT/Claude, conforme a orientação do utilizador associada ao professor Borbinha, sobre o inventário completo elegível. Não assumir que o método concreto do professor, os modelos, a interface ou as condições de privacidade já foram fornecidos. Qwen continua reservado para futuras experiências locais de classificação; a implementação antiga de anotação dos 40 é histórica e suspensa, não o protocolo atual da 19c.

As propostas são SILVER e conservam labels específicas/múltiplas, REFERENCE principal, `other_roles`, evidência, âmbito e incerteza. Não enviar sugestões lexicais. Consenso LLM ou concordância lexical não são accuracy/F1 sem gold independente; não avaliar Qwen contra as suas próprias propostas como se fossem gold. O segmentador de Martim continua posterior ao baseline.

Preparação privada, inspeção de privacidade e autorização de transmissão são etapas separadas. Não enviar textos nesta consolidação, não instalar modelos nem treinar. A ausência de formação jurídica não torna uma saída LLM validada por humano.

## D23 — Consolidar sem perder história nem confundir checks em falta (16-11-2026)

Preservar os relatórios agregados de preparação, exportação e recuperação como snapshots datados; não os apresentar como o inventário integral ou como anotação concluída. O protótipo Qwen, testes e wrapper ficam preservados e identificados como suspensos. A autorização posterior cobre as correções, quatro commits separados e push após validação; não autoriza iniciar 19c, inferência ou transmissão. A [revisão de consolidação](experiment_19c_consolidation_review.md) conserva os problemas encontrados e documenta a sua resolução.

No planeador corrigido, `null`/`not_requested`/indeterminado nos checks gold/piloto produzem revisão explícita; reservas e motivos propagam-se por documento/hash/bloco/processo e aliases. Todas as menções continuam nos planos, sem splits ou elegibilidade de treino automáticos. Labels/propostas pré-preenchidas não são aceites como inventário independente não anotado.

Vincular inputs por IDs e hashes derivados, documentos e previsões aceites do mesmo bundle, contexto e fontes originais pelos hashes do manifesto; persistir fingerprints no novo plano. A contagem não basta. Fontes/companheiros em falta ou alterados são erro, não motivo para repetir NER ou confiar silenciosamente. Isto verifica consistência/rastreabilidade, não autenticidade criptográfica contra substituição fraudulenta de todo o bundle. Antes dos splits definitivos, rever reservas por conteúdo e processos relacionados, com aliases/conflitos; conservar gold50 e as dez revisões piloto. A consolidação não executou o planeador nos dados reais.

## D24 — Primeiro piloto 19c com Qwen local, antes de ampliar (16-11-2026)

Nova direção explícita do utilizador: implementar e preparar 30 ocorrências do inventário integral 19b para Qwen3-8B local no INESC, usando taxonomia v2 e respostas JSON, antes da anotação massiva e de GPT/Claude. Isto sucede à suspensão geral para anotação; o executável histórico 19b de 40 continua suspenso. Reutilizar o loader e helpers de inferência, sem alterar o NER ou benchmarks. Código/testes/documentação podem ser committed e enviados para origin/develop após validação.

Seleção seed 42 por variedade de pistas, nunca gold lexical; um contexto por grupo processual relacionado, preservando IDs/offsets/proveniência originais. Verificar o bundle real, hashes das referências protegidas e exclusões novas explícitas. Não converter `null/not_requested` em resultado negativo. Referências sem raiz/associação verificável exigem resolução privada explícita de proveniência; não descartar a pendência nem presumir ausência. Nenhuma ocorrência automaticamente validada para treino ou convertida em gold.

Prompt versionado 19c-v1: dez classes incluindo REFERENCE principal, multi-label apenas sustentado, `other_roles` literal, evidência e âmbito por atribuição, ambiguidade/insuficiência/entidade inválida separados de UNKNOWN. Checkpoint imutável local, FP16 explícito, greedy/temperatura 0/thinking desativado, limites sem truncagem. Todos os resultados são SILVER, com raw output, parsing e configuração; qualquer output inválido permanece registado, sem reparação ou coerção para UNKNOWN.

GPU apenas em Slurm autorizado. Verificar plano, referências, recursos/cache e preflight de carregamento/template/comprimento dos 30 antes de submeter a geração. Nesta sessão a autenticação SSH não interativa foi recusada; não houve inspeção remota dos dados/recursos, amostragem real, carregamento, downloads ou submissão. [Protocolo e comandos](experiment_19c_qwen_pilot.md). Testes sintéticos/mocks não demonstram inferência real nem qualidade jurídica. Não enviar dados a APIs nem começar treino/anotação massiva nesta fase.

O agregado do job 15216 já está disponível localmente desde o commit preexistente 4b339d3 e foi consultado: `reference_checks.gold=not_requested` e `reference_checks.pilot=not_requested`. Esta evidência reforça a nova verificação explícita da 19c; não converter os null da extração em exclusões verificadas. A inspeção deste agregado não substitui o bundle privado remoto nem inventa um resultado de anotação.

## D25 — Diagnosticar três pendências sem remover proteções

O utilizador comunicou seleção bloqueada no g09: 111 referências, 108 resolvidas, três pendentes, 15 grupos bloqueados, zero selecionados e zero chamadas LLM. O manifesto privado não está neste workspace; não inferir a origem/causa das três. Criar diagnóstico reproduzível a partir do manifesto e fingerprints originais. Só códigos, contagens e tokens HMAC com chave privada aleatória podem aparecer no JSON partilhável; mapa/evidência/chave ficam ignorados no INESC. Não usar SHA simples de IDs adivinháveis nem imprimir nomes/excertos/processos.

Reservar positivamente todos os documentos correspondentes após reconciliação de formatação/documento/processo verificável, com método e hashes na auditoria. Não declarar ausência por pesquisa sem resultado, não promover similaridade a identidade e não escolher silenciosamente uma só versão. Mantêm-se a gate de zero pendências, os grupos/aliases e a exclusão de identidade incerta. Não alterar selection_complete manualmente nem remover referências.

Adjudicações novas devem estar vinculadas à referência/inventário atuais e a evidência privada local conferida por hash. Uma reserva documental exige pacote de julgamento humano ligado aos hashes das fontes; integridade não prova semanticamente identidade e o revisor deve verificar o vínculo. Alegar fonte externa exige documento com excerto correspondente, cabeçalho inequívoco e nenhuma raiz/hash/match conhecido no corpus; fontes desconhecidas do corpus continuam fora da seleção. Declarações sem evidência, stale ou conflitantes são erro. Não alterar NER/GOLD/revisões nem inferir labels jurídicas. Ver [protocolo de diagnóstico e comandos](experiment_19c_protection_diagnostic.md).
