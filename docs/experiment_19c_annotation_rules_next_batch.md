# 19c: regras de trabalho para o próximo lote

Política **19c-legal-role-policy-v1**, 19-11-2026. O utilizador pediu fechar as ambiguidades e confirmou o foco em papéis jurídicos, não relações pessoais. São convenções operacionais de anotação; não constituem validação humana de cada registo nem uma política institucional de anonimização.

Preservar as dez classes de role_taxonomy_v2.json, parser, prompts v1/v2 e outputs históricos. Estas clarificações são implementadas no novo prompt **19c-v3-legal-roles**, ainda não executado. [Builder, auditorias e limites](experiment_19c_v3_preparation.md).

## Unidade e evidência positiva

Classificar a ocorrência PER marcada no contexto fornecido. Não usar conhecimento externo sobre a pessoa nem transferir papéis de vizinhos/processos. Aceitar múltiplas classes quando cada uma tem suporte positivo para o alvo, com evidência/âmbito próprios. Outra ocorrência inequivocamente correferente na mesma janela pode sustentar o papel; nomes repetidos não resolvem homónimos automaticamente. Deduplicar e ordenar pela taxonomia. UNKNOWN é exclusivo nas classes principais.

## UNKNOWN e abstenção

| Resultado | Critério operacional |
|---|---|
| supported com classe específica | Cada papel está sustentado para o alvo. |
| supported com UNKNOWN | Pessoa válida, ocorrência narrativamente inteligível, nenhuma das nove classes específicas sustentada e nenhum défice observável de contexto que impeça interpretar a ocorrência. Pode haver papel jurídico fora da taxonomia. |
| insufficient | Falta informação decisiva: tabela sem cabeçalhos, fragmento cortado no ponto relevante, antecedente indispensável ausente ou contexto ininteligível. Explicar concretamente o que falta. |
| ambiguous | Há evidência para interpretações concorrentes de papel/associação, sem base para escolher. UNKNOWN não resolve esse conflito. |
| invalid_entity | O span não é uma pessoa única utilizável, por exemplo organização, pessoas fundidas ou nome com cabeçalho/código incorporado. Não reparar silenciosamente. |

UNKNOWN é limitado à janela: não afirma que a pessoa nunca teve um papel no documento completo. A possibilidade abstrata de existir informação adicional não torna todas as menções insufficient. Participar numa narrativa criminal não demonstra ARGUIDO.

UNKNOWN mantém a estrutura histórica: única classe, evidence/scope=not_applicable, quote vazia, status=supported, uncertain=false. insufficient/invalid_entity exigem listas vazias, uncertain=true e motivo. ambiguous exige uncertain=true; atribuições são tentativas. Papel claro com âmbito incerto pode manter status=supported, scope=uncertain e uncertain=true; não o converter em UNKNOWN. Dificuldade de leitura não é, por si, incerteza da decisão.

## other_roles: apenas funções ou estatutos jurídicos

Conservar designações jurídicas relevantes fora das classes principais: assistente, vítima, ofendido, denunciado, advogado, juiz ou um papel contratual como comprador. Exigir designação literal no contexto, citação literal e âmbito. Não é uma whitelist lexical: a associação ao alvo e o uso concreto precisam de suporte.

Excluir parentescos/relações afetivas, ocupações genéricas e descrições narrativas como irmã, companheira, conhecido ou uma frase construída sobre a conduta. Esses factos podem ajudar a interpretar o texto sem virarem labels jurídicas.

Não repetir classes principais em other_roles nem acrescentar apenas o título/hierarquia do mesmo exercício funcional: com RELATOR na assinatura, Juiz Conselheiro não é um segundo papel só por ser o título que o acompanha. Uma função judicial distinta e não coberta por classe principal pode ser preservada literalmente. Um estatuto adicional diferente, como condenado, pode ser conservado quando sustentado; condenação isolada não prova ARGUIDO no processo atual.

Se só houver papel jurídico fora da taxonomia, usar UNKNOWN mais other_roles. Uma menção inteligível apenas familiar/narrativa, sem classe específica sustentada e sem défice concreto de contexto, recebe UNKNOWN com other_roles vazio. Não inventar vítima/ofendido em other_roles quando a designação não consta do texto, mesmo se a narrativa descreve uma agressão.

## Âmbito por atribuição

- current_proceeding: papel na causa em análise ou na sua cadeia processual identificável. Transcrever uma decisão anterior da mesma causa não cria, por si só, outro processo.
- cited_proceeding: papel positivamente ligado a uma causa/processo distinto ou precedente referido.
- both: o mesmo papel tem apoio nos dois âmbitos; não é um substituto de dúvida.
- uncertain: o papel tem apoio, mas não é possível ligá-lo com segurança ao processo atual ou distinto. Usar uncertain=true e motivo.
- not_applicable: obrigatório para UNKNOWN e REFERENCE.

Passado temporal e processo distinto são dimensões diferentes. Uma constituição histórica como arguido, sem ligação processual demonstrada, mantém scope=uncertain. Uma ação laboral descrita como ação distinta pode ter scope=cited_proceeding sem inventar o seu ID. A atribuição de splits continua sujeita às verificações próprias de proveniência/famílias.

## AUTOR e REFERENCE

AUTOR cobre a parte que intenta a ação declarativa não criminal, incluindo a ação laboral quando esse estatuto está sustentado. Não confundir com autor de crime, obra ou texto. REU é a parte demandada nessa aceção não criminal, nunca um arguido criminal. Não substituir o estatuto sustentado de AUTOR laboral por REQUERENTE apenas por ser jurisdição laboral.

A inclusão neste mapeamento é uma convenção operacional de anotação, não equivalência de todas as formas processuais nem parecer jurídico. Não aplicar por analogia a procedimentos que a passagem não sustente; validação com os responsáveis metodológicos continua necessária.

REFERENCE não exige título/ano/página se há atribuição inequívoca de posição/definição doutrinária a um autor, num contexto bibliográfico/doutrinário. Usar inferred se a autoria de obra/artigo não está diretamente identificada. Não transformar qualquer pessoa que fala de direito em autor bibliográfico: declarações de partes/testemunhas, argumentos de advogados e decisões judiciais não bastam. Se a natureza da atribuição não se resolve, aplicar ambiguous/insufficient conforme a causa da dúvida.

## Citações e revisão derivada

O parser original continua literal: citação contínua até 240 caracteres, sem marcadores, preservando caracteres, whitespace e pontuação. Falha de cópia não prova papel errado. Guardar separadamente avaliação do papel e conformidade.

Correções posteriores ficam em artefacto privado derivado com fingerprint original, política, resposta proposta e offsets literais. Recuperação automática só tolera o que a sua versão documenta e exige correspondência única; não alargar silenciosamente pontuação. Propostas assistidas que passam no parser continuam human_validated=false até confirmação humana por anotação.

## Próximo lote e implementação

O [planeador de 100](experiment_19c_next100_plan.md) inventaria IDs/pendências; não certifica 100 elegíveis. Revalidar reservas e excluir Gold50, piloto humano, 30 de desenvolvimento e documentos/famílias/duplicados relacionados. Contar capacidade antes da quota. Não repetir NER ou alterar famílias para obter 100.

Uma decisão insufficient ou scope=uncertain fecha o que é possível decidir com a evidência atual; não obriga a adivinhar. Qualquer contexto ampliado deve ser derivado/versionado, sem substituir o original. O piloto continua desenvolvimento, não teste independente sob v3. Preservar 26/30 como conformidade original IAedu; não atualizar essa métrica com propostas corrigidas.

Schema, taxonomia, prompts históricos, autorizações e contrato de 30 dos runners permanecem inalterados. A implementação offline nova reutiliza a infraestrutura e não seleciona/executa 100 nem estabelece treino. Regras semânticas no prompt não são verificadas integralmente pelo parser literal.
