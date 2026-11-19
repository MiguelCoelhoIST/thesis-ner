# 19c — regras v3, revisão privada e capacidade do próximo lote

19-11-2026. Preparação offline, sem chamadas, inferência ou transmissão. O patch documental fornecido foi incorporado e atualizado para distinguir a implementação atual das intenções anteriores. Os materiais privados do ZIP estão exclusivamente em data/raw, ignorado pelo Git.

## Verificação realizada localmente

O verificador `src/annotation/verify_assisted_review_19c.py` comparou a revisão assistida com os ficheiros originais IAedu e o input portátil disponíveis neste computador. Verificados hashes de previsões/run/parser, fingerprints canónicos dos registos, texto, metadata/proveniência do input, alvo/offsets, raw, outputs interpretados e citações/offsets propostos. A mudança esperada de annotation_tier de UNANNOTATED para SILVER é explícita; nenhum outro campo do input pode mudar. Todas as ocorrências literais de uma citação são registadas, sem escolher ou reparar uma correspondência.

Resultado: **13/13 verificadas**, **10 propostas alteradas**, **3 mantidas**, sem erros. O parser histórico reproduziu as flags dos **30 outputs**, e o agregado original continua **26/30 conformes**. A auditoria final derivada está em `data/raw/experiment_19c_rules_review_verification03/verification_PRIVATE.json`. Os ensaios anteriores foram conservados privadamente; o primeiro rejeitava também a transição esperada de annotation_tier, corrigida no verificador, sem modificar dados.

Isto comprova integridade/conformidade, não correção jurídica: todas as propostas continuam human_validated=false, requires_review=true e treino NOT_ESTABLISHED. Os outros 17 casos não receberam revisão semântica nova. Não foram auditados os corpos/eventos HTTP. Backend permanece desconhecido; a etiqueta da UI não é identificação do modelo. Não se alteram previsões, raw, autorizações ou métricas históricas.

## Prompt novo

`config/prompts/role_annotation_19c_v3_legal_roles.txt` implementa as [regras operacionais](experiment_19c_annotation_rules_next_batch.md), preservando dez classes, multi-label, schema e abstenções. `src/annotation/prompt_19c_v3.py` expõe build_messages(record) e configuration(): alvo antes do mesmo contexto marcado, validação histórica de input/offsets, versão e hashes de prompt/builder/parser/taxonomia. Não recebe pareceres nem propostas no pedido e rejeita suggested_label.

V1/v2 e os executáveis/cápsulas/checkpoints anteriores ficam intactos. Não há nova execução ou exportação v3: a integração com um futuro runner de 100 deve ser explícita, versionada e autorizada depois da seleção. Não mudar o prompt de um runner retomável já iniciado.

Limites: o parser confirma schema/citações, não associação jurídica, relevância de other_roles ou classificação correta do âmbito. UNKNOWN exige uncertain=false; combinar exclusivamente papéis fora da taxonomia com âmbito incerto pode revelar uma limitação do schema histórico. Não inventar scope para o satisfazer: manter esse caso para revisão/decisão metodológica. Nenhuma alteração de parser foi feita para o resolver silenciosamente.

## Inventário antes das próximas 100

`src/annotation/audit_next100_19c.py` reutiliza load_bound_inventory, load_pilot, assess_protection, group_index e content_related. Exige inventário NER completo, fontes originais intactas, Gold50/piloto humano congelados, seleção/input originais dos 30 e adjudicações privadas quando necessárias. Não usa labels propostas como evidência e não gera pedidos ao LLM.

As famílias ligadas por documento, hash, blocos, raízes/aliases e reservas conhecidas são protegidas. Uma semelhança de conteúdo em qualquer ocorrência reserva o grupo inteiro; as contagens de motivos não são disjuntas. Pendências de identidade propagam-se por grupo. Checks not_requested/null originais ficam registados, e só uma revalidação explícita das referências pode produzir capacidade exploratória; referências por resolver mantêm uma gate global. Não estabelece splits definitivos ou ausência de relações ainda desconhecidas.

Escreve, num diretório privado novo:

- mention_capacity_PRIVATE.jsonl: todos os IDs/offsets de documento, hashes de contexto, grupos e motivos, sem seleção ou remoção silenciosa;
- audit_PRIVATE.json: bindings, referências/reservas e agregado de capacidade, sem labels automáticas.

O resumo de stdout contém só contagens/códigos. Contextos repetidos são contados, mantendo ocorrências diferentes. A capacidade de um caso por grupo é um **limite superior**: semelhanças entre futuros selecionados podem reduzi-la. Se houver menos de 100 grupos elegíveis, não flexibilizar a política automaticamente. A auditoria pode levar tempo por comparar conservadoramente contextos; mostra progresso a cada 100 ocorrências e não carrega NER/LLM.

O inventário integral e a evidência privada não estão neste workspace. A tentativa de acesso SSH apenas de leitura ao g09 falhou na resolução DNS, antes de autenticar ou executar comandos remotos. **Não foi executada aqui a auditoria integral, não há contagem nova de elegíveis e nenhum conjunto de 100 foi selecionado.** A preparação local do piloto de 30 não substitui o bundle completo necessário no g09.

No g09, depois de disponibilizar este código e ativar venv-ner, definir os dois caminhos privados reais (sem copiar o seu conteúdo para relatórios públicos):

```bash
cd ~/thesis-ner
source venv-ner/bin/activate
read -r -p 'Selection manifest original dos 30: ' STJ_19C_SELECTION
read -r -p 'Adjudicações de proteção verificadas: ' STJ_19C_DECISIONS
test -f "$STJ_19C_SELECTION" && test -f "$STJ_19C_DECISIONS" && \
python -u src/annotation/audit_next100_19c.py \
  --input data/raw/experiment_19b_ner_full_15216_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_ner_full_15216_manifest.json \
  --pilot-sources data/raw/experiment_19a_candidates_v4_smoke10.jsonl \
  --development-input "$(dirname "$STJ_19C_SELECTION")/pilot_input.jsonl" \
  --development-selection "$STJ_19C_SELECTION" \
  --protection-decisions "$STJ_19C_DECISIONS" \
  --output-dir data/raw/experiment_19c_next100_capacity01
```

Usar a seleção original completa dos 30, não o manifesto portátil. As adjudicações devem ser as provas privadas verificáveis da seleção, não um ficheiro inventado/vazio para contornar pendências. O caminho das fontes do piloto humano é obrigatório para esta verificação; não é dependência da execução NER 19b. Saída 1 com referências pendentes guarda auditoria sem dar elegibilidade; falhas de integridade não criam uma seleção. Escolher outro nome se o diretório já existir. Rever contagens/reservas antes de definir quota/teto por família ou autorizar novas mensagens.

## Testes

Testes sintéticos em tests/test_19c_rules_next_batch.py cobrem fingerprints/raw/offsets, IDs duplicados, citações inventadas, integridade de input, schema multi-label/abstenções, mensagens v3, exclusões e propagação por família, semelhança detetada tardiamente, gate global e rejeição de labels pré-preenchidas. Nenhum modelo/API é chamado. Comandos:

Resultado local: **18 testes específicos passaram**; suite completa **271 testes, sucesso, 1 integração opcional omitida**. git diff --check passou. A verificação de privacidade dos dez ficheiros públicos novos/alterados não encontrou correspondências com os alvos multi-palavra/citações privadas verificadas nem padrão de credencial; isto não constitui uma garantia geral de anonimização do corpus. V1/v2, parser, taxonomia v2 e Gold50 foram comparados com HEAD e preservados. Nenhum dataset ou resultado histórico foi alterado.

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p test_19c_rules_next_batch.py -v
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```
