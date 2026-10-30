# Continuidade do projeto thesis-ner

## Começar uma sessão

1. Ler [docs/THESIS_STATE.md](docs/THESIS_STATE.md) e [docs/DECISIONS.md](docs/DECISIONS.md).
2. Verificar `git status --short` e preservar alterações já existentes.
3. Confirmar o script, a configuração, o dataset e o relatório relevantes antes de afirmar que uma experiência foi executada ou melhorou resultados.
4. Atualizar estes documentos quando o utilizador autorizar uma mudança material de estado ou de metodologia. Distinguir implementação, teste sintético, piloto humano, benchmark e execução completa.

O README e algumas notas antigas descrevem etapas anteriores. Não assumir que a sua lista de labels, ranking de encoders ou próximos passos representam o estado atual. Para resultados, consultar os artefactos específicos e indicar dataset/tamanho/protocolo.

## Objetivo e arquitetura

Tese de mestrado sobre anonimização jurídica portuguesa, NER e classificação contextual de papéis de pessoas:

```text
Text -> Eduardo NER -> PER -> classificador de papéis
```

O modelo NER preferido é o pipeline spaCy local `models/eduardo_extended_model`. Não treinar nem substituir modelos sem pedido. A extração atual exige spans PER desse modelo; não usar expressões capitalizadas ou placeholders como fallback automático de pessoas.

## Regras de dados e investigação

- Preservar datasets, anotações humanas e resultados anteriores. Escrever novas versões; não fazer migrações destrutivas.
- O conjunto `data/eval/roles_eval_real_candidates_v1.jsonl` está congelado: 50 exemplos humanos, 10 por classe histórica. Não alterar, usar como treino, demonstrações few-shot ou seeds de extração.
- A Experiência 19 usa nove papéis finos provisórios definidos em `config/role_taxonomy.json`; a taxonomia agregada deriva automaticamente da fina. Usar os mesmos exemplos e splits na comparação.
- Sugestões lexicais descobrem candidatos; não são gold labels. Só confirmação humana explícita pode validar uma anotação. UNKNOWN, REJECT e uncertain têm significados distintos.
- Ler [o protocolo da Experiência 19a](docs/experiment_19a_annotation_protocol.md) antes de alterar anotação. É uma tarefa mention-level, multi-label, com âmbito processual por label; papéis de processos citados não estabelecem papéis no processo atual.
- Preservar texto e offsets exatos. Não inserir entity markers no texto real armazenado. Derivar `[ENTITY] entity [/ENTITY]` no momento de inferência através de `src/utils/entity_marking.py`.
- Separar `decision_id` de `process_group_id`. Conservar evidência de cabeçalho, nome do ficheiro e referências; não resolver conflitos silenciosamente. Agrupar decisões/incidentes relacionados no mesmo split e rever grupos não resolvidos.
- Não executar corpus real completo, treinos ou benchmarks dispendiosos numa tarefa de documentação. Para extração autorizada, começar por um benchmark limitado e auditável.
- Resultados qualitativos de cinco exemplos ou pilotos de anotação não são métricas de generalização. Não misturar o desafio multi-entidade com os 50 exemplos de headline.

## Privacidade e Git

- Nunca adicionar ao Git dados pessoais dos acórdãos, documentos brutos, textos privados, notas confidenciais de revisão, modelos, checkpoints, caches ou ambientes virtuais.
- Manter corpus, pools, revisões e auditorias locais em `data/raw/`, que está ignorado. `models/`, `venv/` e `venv-ner/` também estão ignorados.
- Usar apenas exemplos inventados em novos testes e documentação; resultados versionáveis devem conter métricas e contagens sem pessoas ou excertos privados. Não copiar exemplos de relatórios antigos para novos documentos.
- O facto de um artefacto antigo estar versionado não autoriza republicar o seu conteúdo. Sinalizar problemas sem reproduzir dados nem apagar ficheiros automaticamente.
- Não enviar documentos privados para APIs, conversores online ou serviços externos sem autorização explícita para essa operação.
- Não fazer commit, push, uploads ou publicação automaticamente. Instruções históricas de sincronização não constituem autorização permanente para essas ações.

## Ambiente, comandos e verificação

- Executar comandos a partir da raiz. Código em `src/`, testes sintéticos em `tests/`, configuração em `config/`, documentação em `docs/` e resumos de experiências em `results/`.
- O ambiente dedicado para NER/GPU chama-se `venv-ner/`. Verificar a sua localização e versões efetivas antes de o usar. Não assumir que o `venv/` histórico tem CUDA ou que o ambiente dedicado está presente em todos os checkouts.
- Sem `--gpu-id`, o extrator exige CPU. Com `--gpu-id 0`, chama `spacy.require_gpu(0)` antes de `spacy.load` e falha se a GPU não estiver disponível. Não introduzir fallback silencioso.
- `--max-documents 10` permite um benchmark determinístico. Usar `--output` e `--audit-json` na mesma execução para não repetir NER apenas para gerar a auditoria.
- Escolher nomes novos para outputs. Confirmar `NER device` no stdout e guardar tempos, versões e parâmetros. Um teste funcional GPU não demonstra desempenho no corpus.
- Testes existentes: `python -m unittest discover -s tests -v`, com o Python do ambiente apropriado. Testes de seleção CPU/GPU usam mocks e não substituem uma execução GPU real.
- Validar apenas na proporção da alteração; não executar inferência ou treino para verificar uma alteração exclusivamente documental.

## Requisito pendente de 30-10-2026

`CITATION_AUTHOR` é uma designação provisória para distinguir autores de obras/artigos citados. Ainda não está implementada, não pertence à configuração atual e não deve ser adicionada a datasets, prompts ou mapeamentos sem uma decisão metodológica explícita. Não confundir com AUTOR processual nem usar UNKNOWN como substituto conceptual. Qualquer sugestão futura de exclusão da anonimização exige validação com os orientadores e o STJ; não preservar identidades automaticamente.
