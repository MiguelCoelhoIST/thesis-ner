# Decisões metodológicas e operacionais

Atualizado em **30-10-2026**. Este registo consolida decisões já presentes no código/protocolos e o novo requisito desta data. Não atribui datas históricas que não estejam comprovadas e não substitui a validação pelos orientadores e pelo STJ.

| ID | Decisão | Estado / fundamento |
| --- | --- | --- |
| D01 | Arquitetura Text -> Eduardo NER -> PER -> classificador de papéis. Manter a deteção de entidades separada da classificação de papéis. | Em uso. [Pipeline](../src/evaluation/pipeline_roles.py), [extrator](../src/data/extract_role_candidates_v2.py). |
| D02 | Preservar as cinco classes históricas e os 50 exemplos reais congelados, sem treino, seeds ou demonstrações com esse conjunto. | Em vigor. Hash e resultados em [THESIS_STATE.md](THESIS_STATE.md); [Experiência 16](../results/experiment_16_real_stj_evaluation_v1.txt). |
| D03 | Na Experiência 19, anotar nove papéis finos provisórios e derivar sete classes agregadas automaticamente, com os mesmos exemplos/splits. | Infraestrutura implementada; comparação ainda sem resultados. [Configuração](../config/role_taxonomy.json), [mapper](../src/data/map_role_taxonomy.py), [plano](../results/experiment_19_plan.txt). |
| D04 | Extrair alvos apenas de spans PER do modelo Eduardo; âncoras lexicais sugerem papéis mas não provam nem entidade nem label. Não usar fallback regex nem inventar divisões de nomes. | Implementado após falhas do piloto heurístico. Auditoria e revisão humana continuam obrigatórias. [Extrator](../src/data/extract_role_candidates_v2.py). |
| D05 | Preservar texto contínuo e offsets exatos; markers são derivados para inferência. Manter IDs, proveniência e outputs versionados. | Em vigor. [Utility](../src/utils/entity_marking.py), [protocolo](experiment_19a_annotation_protocol.md). |
| D06 | A anotação nova é mention-level e pode ser multi-label. Um papel de um processo citado é elegível se suportado, com âmbito registado por label; não implica papel no caso atual. | Implementado no revisor/protocolo. Experiências current-case exigem outra filtragem/adjudicação. [Protocolo](experiment_19a_annotation_protocol.md), [revisor](../src/annotation/review_role_candidates.py). |
| D07 | UNKNOWN é uma pessoa válida sem papel-alvo suportado; REJECT é exemplo/entidade/span inutilizável. Incerteza de label não se converte em UNKNOWN. Apenas confirmação humana explícita valida anotações aceites. | Em vigor. Evidência explicit/implicit, not_applicable para UNKNOWN e uncertain para pendências. [Validador](../src/evaluation/validate_role_candidates_v2.py). |
| D08 | Conservar separadamente o ID exato da decisão e o grupo processual normalizado. Agrupar decisões relacionadas e incidentes no mesmo split; não escolher silenciosamente entre cabeçalho e filename. | Implementado; há conflitos ainda por adjudicar. [Auditor de metadados](../src/data/role_provenance.py), [relatório](../results/experiment_19a_provenance_report.txt). |
| D09 | AUTOR designa o demandante civil, não o autor de um crime ou obra. REU é civil, ARGUIDO criminal. Rever a lacuna de cobertura REU do piloto, sem fabricar dados. | Critério atual; linguagem ambígua exige contexto e revisão. [Protocolo](experiment_19a_annotation_protocol.md). |
| D10 | Diagnósticos multi-entidade ficam separados das métricas dos 50 exemplos; pilotos pequenos não são avaliações estatísticas finais. | Em vigor. [Resultados 16](../results/experiment_16_real_stj_predictions_v1.json), [diagnóstico Qwen](../results/qwen3_8b_multi_entity_diagnostic_v1.json). |
| D11 | Usar `venv-ner` dedicado para NER/GPU; GPU é opt-in, exigida antes do carregamento. Fazer benchmark limitado e auditável antes da extração completa. | Suporte implementado. Teste funcional GPU concluído segundo confirmação do utilizador em 30-10-2026; benchmark GPU de 10 documentos pendente. [Testes com mocks](../tests/test_role_candidate_device.py) validam a seleção, não o hardware real. |
| D12 | O segmentador de Martim será avaliado separadamente após o baseline de taxonomia. | Planeado; não marcado como integrado/avaliado. [Plano 19](../results/experiment_19_plan.txt). |
| D13 | Dados pessoais, documentos brutos, modelos, checkpoints e ambientes nunca entram no Git. Não fazer commits/publicação automaticamente. | Regra permanente do projeto e desta tarefa. [AGENTS.md](../AGENTS.md), [.gitignore](../.gitignore). |
| D14 | Distinguir autores de obras/artigos citados, provisoriamente CITATION_AUTHOR, para eventual sugestão de exclusão da anonimização. | **Novo requisito de 30-10-2026, ainda não implementado.** Fonte: pedido do utilizador nesta sessão. |

## D14: âmbito e questões pendentes

`CITATION_AUTHOR` distingue autoria bibliográfica/citada de AUTOR processual e de UNKNOWN. A designação é provisória; não altera a configuração atual nem legitima a migração automática de labels históricas.

Antes de implementar, validar com orientadores e STJ:

1. Se será papel, atributo independente ou outra camada, e como coexiste com papéis processuais/multi-label.
2. Que evidência distingue autoria de obra/artigo, mera menção, autoria de um facto/crime e participação processual.
3. Como anotar nomes ambíguos, citações incompletas, âmbito e incerteza, sem assumir identidade entre menções.
4. Em que condições o sistema pode sugerir preservação de um nome e como essa sugestão é revista por humanos. Não há autorização para exclusão automática da anonimização.
5. Que dados, métricas, splits e critérios de erro serão usados na avaliação dessa capacidade e da sua interação com a anonimização.

Ainda não existem label/mapeamento aprovados para esta categoria, regras de preservação, novo dataset ou resultados de modelo correspondentes. A taxonomia final e a política de anonimização continuam sujeitas à validação científica e institucional.

## Evidência, conflitos e atualização

- Para resultados, usar o artefacto específico e o seu dataset/protocolo; para a taxonomia em uso, usar `config/role_taxonomy.json`. A configuração atual mantém nove labels e não inclui CITATION_AUTHOR.
- README e notas antigas podem descrever versões anteriores. Não apagar essa história nem promover uma conclusão antiga a resultado global; explicitar a versão relevante em [THESIS_STATE.md](THESIS_STATE.md).
- A confirmação do teste funcional GPU é informação do utilizador; os logs/versionamentos desse ambiente deverão ser preservados localmente no próximo benchmark. Não inferir tempo de execução nem versões instaladas a partir dessa confirmação.
- As dez revisões v4 permanecem como anotadas. Campos de âmbito/evidência/proveniência acrescentados posteriormente não são retroativamente considerados validados.
- Uma adjudicação posterior deve citar a evidência, conservar o valor original e criar uma versão/artefacto separado. Não sobrescrever datasets ou resultados antigos.
- Não incluir neste registo pessoas ou excertos dos acórdãos. Documentar decisões com métricas, contagens e referências seguras a ficheiros.
