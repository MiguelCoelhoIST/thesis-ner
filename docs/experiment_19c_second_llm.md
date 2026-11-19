# 19c — segundo LLM, ensaio cego às propostas anteriores

Preparação de 19-11-2026. O utilizador escolheu GPT ou Claude, apenas preparação de ficheiros privados para inspeção. Modelo/provedor/versão exatos por escolher. Não houve inferência, submissão Slurm, download ou envio externo nesta revisão.

Clarificação mais recente: **Claude manual, preferencialmente IAedu**, com versão a confirmar pelo utilizador. Preparados ficheiros individuais e importador offline; a autorização continua limitada a preparação/inspeção. [Procedimento de gravação e importação](experiment_19c_claude_manual.md). O pacote v2 acrescenta requests/NNN.txt e messages.json, template de sessão e pasta de respostas, preservando as mensagens existentes. A execução/transmissão real não ocorreu.

## Leitura exploratória do relatório fornecido

O relatório privado compara v1/15324 e v2/15344 e declara as mesmas 30 menções/offsets/configurações fora do prompt. Regista 8/30 outputs aceites pelo parser original em v1 e 4/30 em v2, com 21 e 22 registos, respetivamente, com problemas de evidência literal/curta. Declara duplicações de papel em 2 e 5 casos e conflitos da categoria com scope em 3 e 4. Categorias sobrepostas, sem referência humana independente. Os ficheiros de inferência privados não foram verificados neste workspace: são valores declarados no relatório, não uma execução reproduzida nesta sessão.

O relatório identifica melhorias pontuais de associação e persistência de transferências entre pessoas, âmbito, cobertura multi-label e abstenção. Isso não demonstra melhoria semântica global nem que target-first seja inútil. A revisão é assistida, não cega e pendente; conformidade não é accuracy e 4/30 não mede quantos papéis estão juridicamente certos. As três dimensões de citações, alvo e âmbito não devem ser fundidas num único erro.

### Papel errado versus papel não demonstrado

Sem os contextos integrais originais e adjudicação humana, as apreciações seguintes são hipóteses para revisão, não correções aplicadas:

- Nos casos 11 e 30, descrições genéricas ou uma relação familiar não demonstram os papéis propostos. A classificação adequada do parecer é **não demonstrado pelo excerto**, não prova de que a pessoa nunca teve esse estatuto. Não converter automaticamente para UNKNOWN; pode faltar contexto.
- Nos casos 18 e 22, evidência sobre outras pessoas invalida essa justificação para o alvo. Isso não prova, por si só, falsidade do papel do alvo em toda a decisão. Separar falha de associação da avaliação independente do estatuto.
- Nos casos 13 e 29, a atribuição de uma frase de outra pessoa é uma possível contradição de associação. Ser vítima/ofendido não exclui logicamente outros papéis noutro âmbito ou uma situação multi-label. Não transformar incompatibilidade da evidência numa regra universal de exclusão.
- No caso 10, assistente não é sinónimo de réu civil; trata-se de uma inferência não sustentada por essa designação. A eventual coexistência de outro papel requer evidência própria.
- No caso 2, o problema descrito pode ser sobretudo temporal/processual: papel histórico não estabelece o mesmo papel no processo atual. Rever scope sem eliminar uma categoria eventualmente sustentada no processo citado.
- No caso 20, insuficiência para inferir papel não equivale a entidade inválida. Validar separadamente os limites do span; o parecer sobre a sua integridade semântica também continua pendente.

Uma omissão só é tratada como papel adicional sustentado quando há suporte positivo para o mesmo alvo, com âmbito próprio. Ser concebível não basta. REFERENCE sem obra identificada e a fronteira UNKNOWN/insufficient continuam questões de adjudicação; não se alterou silenciosamente a política nem o parser.

## Pacote independente do modelo

[Preparador local](../src/annotation/prepare_second_llm_pilot_19c.py). Reutiliza o prompt v2 target-first sem o voltar a ajustar a este relatório: mudar só o modelo permite uma comparação mais controlada. Se depois for necessário alterar prompt/template ou decoding, registar como comparação de configurações completas. Modelo e ambiente serão confirmados antes de qualquer execução.

Exige input/manifesto originais vinculados ao run de referência, exatamente 30 IDs/ordem, fonte/offsets, reserva de avaliação e elegibilidade de treino NOT_ESTABLISHED. Reutiliza load_pilot/build_messages existentes, revalida o bundle protegido e hashes antes de escrever. Não lê respostas Qwen nem aceita ficheiro de revisão como argumento.

Saídas num diretório **novo e ignorado** em data/raw/:

- `model_messages_PRIVATE.jsonl`: 30 linhas, cada uma apenas com messages system/user — instruções/schema/taxonomia do prompt, alvo e contexto marcado. Nenhum ID interno, label sugerida, proposta Qwen ou parecer da revisão é incorporado no conteúdo enviado ao anotador. Preservar a ordem; mapear respostas por ordinal fora do prompt.
- `manifest_PRIVATE.json`: ligação privada ordinal/ID, hashes dos registos/mensagens/ficheiros, proveniência, offsets locais/documentais, prompt/parser/taxonomia e estado de seleção do modelo. Não enviar ao LLM.
- `comparison_template_PRIVATE.jsonl`: formulário vazio separado para os quatro eixos abaixo. Não enviar ao LLM.

O texto mantém-se **privado e não desidentificado** para preservar os mesmos contextos. O pacote não está autorizado para serviços externos e não certifica anonimização. Caso se escolha GPT/Claude, primeiro decidir privacidade/autorização: desidentificar muda o input e exigirá uma variante com mapa privado e comparabilidade documentada. Não usar o exportador histórico de 40 exemplos como substituto deste lote de 30.

Clarificação do utilizador: a via pretendida é agora Claude manual, mas só se prepara o material para inspeção local. O manifesto regista `intended_use=CLAUDE_MANUAL_PRIVATE_INSPECTION_ONLY`, preferência IAedu, `privacy_review_status=PENDING` e `external_transmission_authorized=false`. O JSONL não deve ser carregado nem colado num serviço externo nesta fase. Manifesto e formulário de comparação nunca integram o input do modelo. Não foi autorizada desidentificação nem alteração dos contextos nesta clarificação.

Na raiz do g09, com venv-ner ativo e o código disponível:

```bash
python -u src/annotation/prepare_second_llm_pilot_19c.py \
  --input data/raw/experiment_19c_pilot03/pilot_input.jsonl \
  --selection-manifest data/raw/experiment_19c_pilot03/selection_manifest.json \
  --reference-run data/raw/experiment_19c_pilot_15324/run.json \
  --output-dir data/raw/experiment_19c_second_llm_package01
```

O caminho pilot03 é o indicado no histórico; tem de corresponder aos hashes do run original. Este comando não carrega NER/LLM e imprime apenas contagens/estados. O bundle real só existe no INESC, pelo que o pacote real não foi gerado nesta sessão. Nenhum benchmark ou resultado histórico é alterado.

## Protocolo de comparação

| Eixo | Verificação | Limite da conclusão |
|---|---|---|
| 1. Formato e citações | Aplicar parse_response original ao raw com texto original: JSON/schema, taxonomia, duplicações e citações contínuas exatas de até 240 caracteres. Guardar cada erro, mesmo com resposta inválida. | Citação literal e JSON válido não provam atribuição correta. Não misturar recuperação de evidência só num dos modelos. |
| 2. Associação ao alvo | Rever cada papel e evidência: alvo, outra pessoa ou ligação incerta. Registar supported, not_demonstrated, contradicted ou unresolved para cada afirmação. | Não demonstrado não significa falso; asserção sobre outra pessoa não prova ausência do papel no alvo. |
| 3. Âmbito | Separar regras mecânicas (p.ex. REFERENCE/not_applicable) da interpretação current/cited/both/uncertain. Rever papéis históricos e transferências entre processos. | Scope aceito pelo parser não prova que o enquadramento processual esteja certo. |
| 4. Cobertura e abstenção | Procurar cada papel adicional positivamente sustentado, other_roles e adequação de UNKNOWN/ambiguous/insufficient/invalid_entity. | Não completar labels por suposição; ignorância do papel não torna um span inválido. |

Guardar modelo/provedor e versão/checkpoint, configuração efetiva, seed quando possível, template/chat, hashes, raw, erros e tempos. Registar os conteúdos efetivos system/user e eventual modificação pelo provedor, sem enviar as respostas anteriores. O parser histórico permanece intacto; não usar proposal sem adaptação de proveniência, pois a função histórica identifica explicitamente Qwen como origem. As respostas do novo modelo serão SILVER, human_validated=false e revisão pendente.

Rever também respostas inválidas: um problema de whitespace pode coexistir com papel plausível; corrigir representação não corrige semântica. Discordância/concordância entre modelos serve para triagem, não constitui gold ou validação humana. Preservar dois pareceres quando houver dúvida, sem sobrescrever outputs. Estas 30 menções já orientaram desenvolvimento; não são teste independente nem autorizam treino ou libertação de grupos protegidos. Não calcular accuracy/F1 sem gold adjudicado.

## Validação local

224 testes, sucesso, 1 integração opcional omitida; 5 testes novos com dados inventados. Cobrem separação entre mensagens e metadados/pareceres, manutenção dos 30 IDs/offsets, ausência de inferência, proteção e hashes, output privado novo e stdout agregado. Modelo e via de execução continuam pendentes de escolha; nenhum job ou API foi executado.
