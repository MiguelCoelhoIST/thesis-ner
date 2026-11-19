# 19c — preparação de até 64 menções com prompt v3

Resultado comunicado pelo utilizador no g09: **3.033 menções disponíveis, 64 grupos, zero referências pendentes**, em data/raw/experiment_19c_next100_capacity01/. Não se verificou o artefacto remoto nesta sessão e não se afirma que 64 já tenham sido selecionadas.

## Implementação

- src/annotation/prepare_batch_19c_v3.py: valida auditoria/fontes/referências, seleciona deterministicamente e exporta cápsula privada v3;
- src/annotation/run_iaedu_batch_19c_v3.py: check-only ou execução futura/retoma para o número efetivo, entre 1 e 64;
- tests/test_19c_v3_variable_batch.py: casos inteiramente inventados e HTTP injetado.

Os ficheiros de execução anteriores, prompts v1/v2/v3, parser e resultados não são modificados. Reutilizam-se load_bound_inventory, load_pilot, assess_protection, content_related, construção de mensagens v3, transporte IAedu e as funções históricas de lock/recuperação de captura. Não há nova pipeline NER/modelo/parser. A lógica de orquestração tem contrato novo para não invalidar hashes e checkpoints do piloto de 30.

## Seleção e limitações

Antes da seleção, validar os hashes de todos os bindings do audit_PRIVATE.json, inventário completo, fontes, Gold50/piloto humano congelados, seleção dos 30 de desenvolvimento e adjudicações. Revalidar referências/reservas e comparar as evidências com a auditoria. Verificar cada ID/offset/hash/grupo/motivo do mention_capacity_PRIVATE.jsonl, não apenas as contagens. Falta de fontes ou pendências impede preparar o lote.

As reservas por semelhança de contexto ao material protegido são conservadas da auditoria local concluída; não se repete o passe caro no corpus. Esta verificação é consistência/proveniência de um artefacto local confiável, não autenticação contra substituição maliciosa de todo o bundle e respetivos hashes.

Ordenação estável por SHA-256(seed, tipo, identificador), com seed **42** e desempate por ID. Percorrer os grupos por essa ordem e os respetivos candidatos também por hash. Escolher o primeiro candidato sem contexto igual/semelhante aos já selecionados, usando content_related histórico. Se falhar, tentar outro candidato do mesmo grupo. Nunca escolher duas ocorrências do mesmo grupo ou relaxar exclusões para chegar a 64.

O algoritmo é sequencial, não procura uma solução global máxima: pode obter menos de 64 mesmo existindo outra combinação. Registar o total efetivo, grupos não representados e uma disposição para cada menção disponível: selected, selected_context_similarity, group_already_represented ou requested_group_limit. Para semelhanças, guardar o primeiro ID selecionado em conflito, apenas no manifesto privado. Preservar também as contagens de exclusões da auditoria original, com motivos não disjuntos. Nenhuma pista lexical é convertida em label e não há quota de UNKNOWN/REFERENCE.

Texto, alvo, offsets, IDs, hashes e proveniência são conservados; acrescentam-se cohort e batch_selection próprios. Campos gold permanecem vazios/human_validated=false. O lote é desenvolvimento SILVER, não gold nem conjunto autorizado para treino/splits finais.

## Preparar no g09 — sem chamadas

Depois de disponibilizar estes novos ficheiros no checkout remoto, executar da raiz. Não usar os executáveis antigos de 30 nem repetir NER/auditoria integral:

```bash
cd ~/thesis-ner
source venv-ner/bin/activate

python -u src/annotation/prepare_batch_19c_v3.py \
  --audit-dir data/raw/experiment_19c_next100_capacity01 \
  --max-mentions 64 \
  --seed 42 \
  --output-dir data/raw/experiment_19c_v3_batch01
```

O diretório tem de ser novo e ignorado pelo Git. Inputs e auditoria originais não são alterados. Saídas:

```text
data/raw/experiment_19c_v3_batch01/
  selection_manifest_PRIVATE.json
  capsule/
    batch_input.jsonl
    portable_manifest_PRIVATE.json
    authorization_TEMPLATE_PRIVATE.json
    requests/001.txt ... NNN.txt
```

selection_manifest_PRIVATE.json conserva método/seed, IDs escolhidos, todas as disposições, contagens/grupos, bindings da auditoria/fontes e configuração do prompt. A cápsula contém só as menções escolhidas/pedidos/manifesto/template, nunca o corpus ou referências gold. Os pedidos são instruções v3, alvo e contexto, sem suggested_label/propostas anteriores/pareceres. Contêm texto privado, não são automaticamente anonimizados ou autorizados para transmissão.

O resumo imprime selected, selected_groups, motivos e capsule_manifest_sha256. Conservar esse digest por canal separado para validar uma eventual cópia Windows. Fazer a verificação offline no g09:

```bash
STJ_19C_V3_CAPSULE=data/raw/experiment_19c_v3_batch01/capsule
STJ_19C_V3_DIGEST=$(sha256sum "$STJ_19C_V3_CAPSULE/portable_manifest_PRIVATE.json" | cut -d ' ' -f 1)

python -u src/annotation/run_iaedu_batch_19c_v3.py \
  --capsule-dir "$STJ_19C_V3_CAPSULE" \
  --expected-manifest-sha256 "$STJ_19C_V3_DIGEST" \
  --check-only
```

check-only não necessita de chave, configuração API ou GPU. Verifica ficheiros/IDs únicos/spans, pedidos v3 exatos, hashes de código normalizados CRLF/LF, grupos únicos e semelhança entre contextos. Quando se copia a cápsula para Windows, comparar com o digest obtido no g09, não confiar só num hash calculado depois da cópia. A configuração original do prompt conserva os hashes em bytes do ambiente fonte; a verificação de código portátil usa hashes LF.

## Percurso API preparado, não executado/autorizado

O runner novo conserva os pedidos, capturas HTTP/eventos/raw/metadados, UUID/thread novo por menção, parser literal sem reparação e progresso ordinal/N. Grava resultados/checkpoints por ocorrência e bloqueia reenvio automático de dispatch incerto. Retoma reaproveita capturas duráveis sem chamadas duplicadas; não há garantia exactly-once do servidor sem contrato de idempotência. Os contadores e intervalos usam N efetivo, incluindo N superior a 30.

O template exige scope STJ_19C_V3_BATCH_IAEDU_API, versão v3, N exato, digest desta cápsula, endpoint/canal, revisor/data e aprovações explícitas de privacidade/transmissão. Começa com ambas false e não aceita a autorização dos 30. Configuração/chave continuam apenas em variáveis de ambiente. Etiqueta da UI mantém-se separada dos metadados de backend realmente devolvidos. SILVER/human_validated=false/revisão pendente/treino NOT_ESTABLISHED continuam obrigatórios.

Uma execução futura requer --execute, autorização nova e run-dir novo; --resume só se aplica ao mesmo digest/configuração/autorizações, sem modificar snapshots. **Não executar esses modos nesta etapa.** Aqui prepararam-se apenas código e testes offline; nenhuma transmissão, anotação ou chamada real foi feita.

## Validação local

**17 testes específicos passaram**; suite completa **288 testes, sucesso, 1 integração opcional omitida**. Testam ordem determinística independentemente da ordem do input, até 64 grupos, redução por semelhança, alternativas no grupo, fontes alteradas, falso estado de elegibilidade e pendências, preservação das fontes, cápsula v3 de tamanho efetivo, rejeição de autorização antiga e checkpoints/retoma/raw sem reparação. O transporte é sempre simulado/injetado. Nenhuma seleção real a partir das 3.033 menções foi executada neste workspace.

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p test_19c_v3_variable_batch.py -v
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```
