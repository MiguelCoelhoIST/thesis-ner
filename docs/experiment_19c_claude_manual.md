# 19c — pedidos individuais para Claude manual

Preparação de 19-11-2026. Preferência do utilizador: Claude através do IAedu; a versão disponível será confirmada pelo utilizador. Não se consultou nem se assumiu a interface, o catálogo de modelos ou as garantias de tratamento de dados dessa plataforma. Nesta etapa apenas se preparam ficheiros privados para inspeção; não há autorização de transmissão, browser automation ou API.

## Gerar e inspecionar, sem enviar

Com o código disponível na raiz do g09 e venv-ner ativo:

```bash
python -u src/annotation/prepare_second_llm_pilot_19c.py \
  --input data/raw/experiment_19c_pilot03/pilot_input.jsonl \
  --selection-manifest data/raw/experiment_19c_pilot03/selection_manifest.json \
  --reference-run data/raw/experiment_19c_pilot_15324/run.json \
  --output-dir data/raw/experiment_19c_claude_manual_package01
```

Exige os inputs originais e hashes protegidos. Mantém os 30 IDs/ordem, texto, alvo, offsets e taxonomia. Não recria candidatos, não usa propostas Qwen como demonstrações e não altera o prompt v2. Escolher sempre um diretório novo. O bundle privado real não existe neste workspace, pelo que aqui apenas se testou com dados inventados, sem gerar os pedidos reais.

O pacote contém:

- `requests/001.txt` até `030.txt`: um pedido por menção, composto exatamente pelo conteúdo system v2, duas quebras de linha e o conteúdo user target-first/contexto marcado. Não inclui cabeçalhos de revisão, identificadores internos ou propostas anteriores.
- `requests/001.messages.json` até `030.messages.json`: os mesmos conteúdos como system/user separados, para uma interface que permita essa separação. Não pressupor que o IAedu a suporta.
- `model_messages_PRIVATE.jsonl`: as mesmas 30 mensagens em formato estruturado; não colar o lote inteiro numa conversa.
- `manifest_PRIVATE.json`: correspondência privada entre ordinal e ID original, offsets/proveniência e hashes de ambas as representações.
- `session_TEMPLATE_PRIVATE.json`: modelo vazio para registar versão/modalidade reais. Copiar para `session_PRIVATE.json` sem editar o template de referência.
- `raw_responses/`: pasta inicialmente vazia para as respostas originais futuras.
- `comparison_template_PRIVATE.jsonl` e `MANUAL_README_PRIVATE.md`: avaliação pendente e instruções locais. Nunca os entregar ao modelo.

Inspecionar localmente todos os pedidos e possíveis identificadores residuais. Os textos são privados e não desidentificados; o manifesto mantém `external_transmission_authorized=false` e revisão de privacidade pendente. Não os carregar/colar em Claude/IAedu nesta fase. Uma eventual autorização e verificação de privacidade são separadas. Se for necessário desidentificar, preparar uma nova variante com mapeamento privado: não alterar silenciosamente estes contextos/offsets ou alegar comparação de inputs idênticos.

## Futuro procedimento manual, apenas depois de autorizado

1. Confirmar o nome/versão que a plataforma apresenta, plataforma, data e controles disponíveis. Não inventar checkpoint, seed ou temperatura. Se não forem divulgados/expostos, registar `not_disclosed`/`not_exposed`. A etiqueta da interface não certifica um checkpoint imutável do backend.
2. Iniciar uma conversa nova por menção, com o mesmo modelo e modalidade nos 30 casos. Não usar a conversa de revisão, projetos com pareceres, respostas Qwen ou exemplos corrigidos. Registar instruções adicionais/ferramentas da plataforma conhecidas; caso contrário `not_disclosed`.
3. Se só houver uma caixa de chat, copiar integralmente apenas `requests/NNN.txt`, sem reescrever ou resumir. Registar `message_delivery=single_user_message`. Se houver suporte real a system/user, usar os conteúdos de `NNN.messages.json` nos respetivos campos e registar `separate_system_user`. Não misturar modalidades no mesmo lote.
4. Guardar a primeira resposta completa do assistente em `raw_responses/NNN.txt`, UTF-8 sem BOM. Não incluir botões/elementos da interface. Conservar markdown, cercas de código, citações inválidas, mensagens de recusa, JSON malformado e espaços/quebras de linha que pertençam à resposta. Não reparar, remover cercas ou substituir por uma segunda tentativa.
5. Manter tentativas adicionais em outro ensaio privado, sem sobrescrever a primeira resposta. Se o modelo/modalidade mudar, suspender e documentar a divergência; este importador pressupõe uma sessão homogénea explicitamente declarada.
6. Preencher `session_PRIVATE.json`: provider Anthropic; model_display_name literal da interface; model_version_or_identifier observado ou not_disclosed; platform efetivamente utilizada; execution_mode manual_chat; message_delivery; fresh_chat_per_mention true apenas se cumprido; generation_controls e platform_instructions_or_tools efetivos; session_date. Não deixar PENDING_CONFIRMATION. A confirmação de execução não é validação humana das labels.

Registar também `response_capture_method` (p.ex. cópia da mensagem integral ou exportação disponibilizada pela UI, se existir). Uma interface pode modificar a representação de Markdown/whitespace antes da cópia. A importação conserva exatamente os bytes do ficheiro recebido, não certifica acesso aos tokens brutos do backend. Documentar esta limitação na comparação de citações; não atribuir automaticamente ao modelo uma alteração introduzida pela interface.

Uma UI com instruções ocultas, controles não expostos e concatenação de system/user difere da execução Qwen local. Comparar configurações completas, sem alegar isolamento perfeito do efeito do modelo ou determinismo não controlável. A concatenação preserva os caracteres dos conteúdos, mas não a hierarquia de papéis do chat.

## Importação offline das respostas guardadas

Guardar/transferir os ficheiros apenas pelo procedimento institucional autorizado para o mesmo armazenamento privado onde os inputs originais continuam disponíveis. Depois, sem API/modelo:

```bash
python -u src/annotation/import_claude_manual_19c.py \
  --package-dir data/raw/experiment_19c_claude_manual_package01 \
  --session data/raw/experiment_19c_claude_manual_package01/session_PRIVATE.json \
  --output-dir data/raw/experiment_19c_claude_manual_import01
```

O importador exige exatamente `001.txt` a `030.txt`, sem ficheiros de respostas adicionais na pasta, e os metadados preenchidos. Não cria respostas em falta. Revalida hashes, mensagens, mapeamento, spans e o bundle protegido. Não alterar hashes para contornar um erro: conservar o pacote original e investigar a divergência.

Saída num diretório novo: cópias **byte a byte** dos 30 ficheiros raw, `silver_predictions.jsonl` e `run.json`. Guarda modelo/versão/modalidade, ordinal/ID, hashes de pedido/raw/registo/código, resposta original, parsing_errors e resumo. Não utiliza a função proposal histórica que identifica Qwen como origem; reutiliza diretamente o mesmo parse_response sem o alterar.

O importador não remove BOM/markdown/cercas nem normaliza whitespace. Invalid outputs permanecem guardados, sem conversão para UNKNOWN. `LLM_calls=0` descreve só a importação offline: não significa que as respostas manuais não envolveram uso anterior do serviço. Importação termina com sucesso mesmo que existam respostas inválidas, assinaladas como `imported_with_invalid_outputs` e no resumo. Isso não é aprovação semântica.

As propostas são SILVER, `human_validated=false`, `requires_review=true` e treino NOT_ESTABLISHED. Manter separados os quatro eixos do [protocolo de comparação](experiment_19c_second_llm.md): formato/citações, associação ao alvo, âmbito, papéis adicionais/abstenção. Sem accuracy/F1 ou consenso convertido em gold. Nenhum output, log, resposta, manifesto ou pedido privado entra no Git.

Validação local desta preparação: **228 testes**, sucesso, **1 integração opcional omitida**. Os 9 testes do pacote/importação usam apenas contextos e respostas inventados: preservação de bytes/offsets/modelo, markdown mantido e rejeitado pelo parser, respostas em falta/adicionais, metadados pendentes, modalidades distintas e alterações de pedidos/mapeamento. Não houve execução no Claude/IAedu nem geração do pacote com os dados reais.
