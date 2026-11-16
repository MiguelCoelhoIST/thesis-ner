# Anotação externa — exportação local desidentificada

**Revisto em 16-11-2026:** documentação do exportador histórico dos lotes 5/40, não do inventário completo da 19c. A CLI ainda usa o validador de candidatos 19a e o default 40; não a executar sobre as menções integrais sem adaptação posterior autorizada. As contagens e suites 89/92 abaixo pertencem às validações históricas. O NER integral já concluiu o corpus (job 15216, confirmação do utilizador), mas não produziu labels jurídicas. Ver [estado atual](THESIS_STATE.md).

## Exportação integral do lote histórico: 40 candidatos

O exportador prepara agora **40 registos por omissão**, na ordem original, sem seleção por papel. Execução local concluída, sem APIs externas:

```powershell
.\venv\Scripts\python.exe src/annotation/export_external_annotation.py
```

Ficheiro único de exemplos: **`data/raw/experiment_19b_external_full01_input.jsonl`**.
Manifesto **estritamente privado, nunca partilhar**: `data/raw/experiment_19b_external_full01_private_map.json`.
Instruções e schema: `data/raw/experiment_19b_external_full01_task.json`.
Relatório agregado: [validação integral](../results/experiment_19b_external_full01_export_validation.md).

Os três outputs privados estão ignorados pelo Git. O JSONL mantém IDs externos únicos EXEMPLO_001–EXEMPLO_040; os IDs internos dos candidatos, texto original, proveniência e edições ficam no manifesto, que permite associar respostas sem expor identificadores originais. O campo suggested_label é excluído do material enviado. Não existem labels gold atribuídas.

Foram verificados 40 offsets, 40 reconstruções exatas e a associação dos 40 IDs à ordem original. Os cinco primeiros exemplos transformados continuam iguais ao piloto preservado. Todos os 92 testes passaram. Não se alteraram datasets, gold50, revisões ou outputs anteriores.

Os detetores diretos não encontraram emails/URLs/processos/IBAN/contactos/datas numéricas/matrículas residuais. Um alerta de capitalização foi investigado em EXEMPLO_018: é formado exclusivamente por pseudónimos gerados concatenados, sem caracteres originais nesse token; rever a legibilidade. Duas fronteiras NER com título de tratamento foram normalizadas preservando o título e a ocorrência-alvo original; esta exceção é restrita a Dr./Dra./Sr./Sra., registada no manifesto, não permite aparar nomes nem resolver sobreposições arbitrárias. As contagens das âncoras dos oito papéis mantêm-se, sem certificar preservação semântica completa.

O JSONL está preparado em formato de partilha, **não certificado como anónimo**. Inspecionar contexto raro, aliases, relações pessoais, organizações/moradas e eventuais omissões NER, além da legibilidade. Não partilhar o manifesto. Nada foi enviado; Qwen permanece suspenso.

```powershell
notepad .\data\raw\experiment_19b_external_full01_input.jsonl
```

O comando de geração já foi executado e recusa sobrescrita. Para repetir, indicar novos nomes em `--output`, `--private-map`, `--task-output` e `--report`. Para um piloto futuro, usar `--limit 5` com novos nomes; por omissão exige 40 disponíveis e nunca reduz silenciosamente a contagem.

## Histórico: piloto de cinco e fronteira de privacidade

Em 30-10-2026 foram preparados os **cinco primeiros registos, na ordem do ficheiro**, de `data/raw/experiment_19a_annotation_batch01_v1.jsonl`. Não houve seleção por papel, anotação, treino ou envio externo. **A execução do Qwen está temporariamente suspensa**, por orientação do utilizador; este piloto destina-se à estratégia de anotação assistida por ChatGPT/Claude.

O resultado é um rascunho de **pseudonimização/desidentificação**, não anonimização certificada. É reversível através de um mapa privado e continua a exigir inspeção integral local antes de qualquer partilha. Factos raros, relações familiares, profissões, localidades, citações e combinações de contexto podem reidentificar pessoas apesar dos nomes removidos. Nunca apresentar sucesso dos testes como garantia de anonimização ou autorização institucional de transferência.

## Histórico: comandos e ficheiros do piloto de cinco

Na raiz do repositório, com o ambiente local que tenha o modelo Eduardo e as dependências existentes:

```powershell
.\venv\Scripts\python.exe src/annotation/export_external_annotation.py
```

Este comando foi executado com sucesso localmente em CPU na versão anterior, que limitava a cinco; a versão atual usa os defaults integrais indicados acima. Não é necessário Qwen nem acesso INESC. Os outputs históricos, preservados e ignorados pelo Git, são:

- `data/raw/experiment_19b_external_pilot01_input.jsonl`: cinco exemplos transformados, IDs opacos, alvo/offsets transformados e texto marcado.
- `data/raw/experiment_19b_external_pilot01_task.json`: instruções e JSON Schema da resposta, com os nove papéis finos e REFERENCE experimental.
- **`data/raw/experiment_19b_external_pilot01_private_map.json`: estritamente privado, NUNCA partilhar.** Contém IDs originais, registos originais, edições reversíveis e metadados do modelo/exportador.

O [relatório agregado](../results/experiment_19b_external_pilot01_export_validation.md) não contém textos, nomes ou IDs processuais individuais.

Para inspecionar o material destinado aos LLMs:

```powershell
notepad .\data\raw\experiment_19b_external_pilot01_input.jsonl
notepad .\data\raw\experiment_19b_external_pilot01_task.json
```

O exportador recusa sobrescrever ficheiros. Para repetir, fornecer **novos nomes para os quatro outputs**, por exemplo:

```powershell
.\venv\Scripts\python.exe src/annotation/export_external_annotation.py `
  --output data/raw/experiment_19b_external_pilot02_input.jsonl `
  --private-map data/raw/experiment_19b_external_pilot02_private_map.json `
  --task-output data/raw/experiment_19b_external_pilot02_task.json `
  --report results/experiment_19b_external_pilot02_export_validation.md --limit 5
```

Não foi feita nem autorizada partilha automática. Depois da inspeção, apenas o input transformado e a tarefa são material potencial de partilha; nunca o mapa, input original, pool, auditorias ou revisões. Confirmar também as condições de utilização/retensão e permissões institucionais da ferramenta escolhida. O procedimento concreto do professor Borbinha ainda não foi fornecido e não se presume equivalente a esta implementação.

## Transformação e consistência

O [exportador](../src/annotation/export_external_annotation.py) reutiliza `load_person_ner()` do extrator, Eduardo NER local (`PER`, `ORG`, `LOC`, `MOR`, `DAT`, `IDP`), `nlp.pipe`, o validador existente, proteção de paths ignorados e `mark_entity()`. Opera nos contextos selecionados: cinco no piloto antigo, 40 por omissão na versão atual; não percorre o corpus. Carregamento offline; sem fallback silencioso para detetar pessoas apenas por capitalização. Esta revisão não executou o exportador.

Pessoas identificadas pelo NER e a ocorrência-alvo exata recebem `PESSOA_1`, `PESSOA_2`, etc. Grafias exatas normalizadas repetidas no mesmo documento usam o mesmo identificador. Não se afirma identidade entre nomes abreviados/completos ou grafias iguais em processos diferentes; esses aliases exigem revisão. A consistência é por documento e superfície, não uma resolução jurídica de identidade.

Para além do NER, regras conservadoras cobrem contactos, emails, URLs, IBAN, matrículas, datas, números e processos. Tokens capitalizados não reconhecidos, fora de uma lista de palavras jurídicas comuns, são ocultados como `DADO`, **não classificados automaticamente como PER**. Isto pode remover palavras contextuais úteis, pelo que é necessário inspecionar o resultado. Números claramente associados a `artigo`/`art.` são preservados para manter pistas jurídicas, exceto quando cobertos por uma identificação mais ampla; esse compromisso não remove o risco de reidentificação.

Substituições sobrepostas são unificadas. Se uma substituição exceder e sobrepor parcialmente o alvo, o exportador falha em vez de inventar novos offsets ou fundir pessoas silenciosamente. Em caso de erro ou dado residual, não contornar a proteção nem partilhar: rever regras/spans localmente e produzir nova versão, sem alterar os datasets originais. Não editar manualmente o texto exportado sem atualizar e revalidar a correspondência privada.

O export contém apenas `id`, `text`, `entity`, `entity_start`, `entity_end`, `marked_text` e `privacy_status`. O ID externo (`EXEMPLO_001`, etc.) evita divulgar IDs internos potencialmente identificantes. O mapa preserva o ID original e os metadados, exclusivamente localmente. As labels sugeridas nunca entram no material de anotação. Os markers são derivados **após** recalcular offsets; não se inserem no dataset original.

## Respostas e reintegração

O JSON Schema da tarefa pede `id`, `labels`, `evidence`, `scope`, `uncertain` e `uncertainty_reason`. Evidência por label inclui tipo explicit/inferred/not_applicable e quote literal curta do texto transformado. Âmbito é definido por label: processo atual, citado, ambos, incerto ou não aplicável. UNKNOWN não substitui ambiguidade; REFERENCE é experimental, não AUTOR processual nem uma decisão de preservar identidades.

`reintegrate_responses(responses, private_map)` faz a associação por ID externo, rejeita IDs desconhecidos/duplicados e conserva respostas como SILVER com `human_validated=false`. É uma **junção por identidade**, não um validador jurídico nem um importador gold: respostas reais ainda precisam de validação do schema, evidência, exclusividade de UNKNOWN e coerência entre labels/âmbito antes de qualquer uso científico. O JSON Schema descreve a estrutura, mas nem todas as restrições semânticas cruzadas são expressas nele.

Os IDs externos são locais a esta exportação. Usar sempre o mapa correspondente e conferir hashes/versão; não misturar lotes diferentes com os mesmos IDs sequenciais. As quotes do LLM referem-se ao contexto transformado, não automaticamente a substrings do original. Os registos originais e offsets originais permanecem no mapa para auditoria; não restaurar dados pessoais numa resposta destinada a ser partilhada.

## Validação e limitações

O piloto passou 5/5 verificações de offsets e 5/5 reconstruções exatas do texto original. O input permaneceu com o hash original; as âncoras dos oito papéis mantiveram as contagens. Isso não comprova preservação de todas as pistas semânticas.

Os [testes novos](../tests/test_external_annotation_export.py) usam apenas exemplos inventados e verificam consistência, outros identificadores, omissão de proveniência/sugestões, sobreposições, reconstrução, reintegração e schema. Não copiam textos dos acórdãos e não enviam dados. O mapa privado e os outputs transformados continuam fora do Git. Não foi produzido gold nem foram modificados o benchmark de 50, as revisões piloto ou o lote original.

Suite histórica do piloto: **89 testes passaram**, incluindo oito novos do exportador; a passagem posterior de 40 registou 92. A verificação complementar dos padrões diretos de email/URL/processo/IBAN/contacto/data numérica/matrícula não encontrou correspondências residuais no piloto; isso não cobre todos os dados pessoais nem substitui a inspeção contextual.
