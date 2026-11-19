# Experiência 19c — agregado IAedu versus Qwen no piloto de 30

Registo de 19-11-2026. Fonte: relatório privado fornecido pelo utilizador, `analise_piloto_19c_iaedu_vs_qwen.md`. Os números abaixo são reportados nesse relatório e confirmados como valores a registar pelo utilizador. Não houve reexecução ou inspeção independente dos ficheiros privados de inferência nesta tarefa. O relatório detalhado, pedidos, respostas e identificadores não são versionados aqui.

## Conformidade com o protocolo original

| Configuração | Menções | Respostas conformes | Não conformes | Taxa de conformidade |
|---|---:|---:|---:|---:|
| Qwen3-8B, prompt v1 original | 30 | 8 | 22 | 26,7% |
| Qwen3-8B, prompt v2 original | 30 | 4 | 26 | 13,3% |
| Agente IAedu, prompt v2 original | 30 | 26 | 4 | 86,7% |

**Conformidade não é accuracy.** Mede aceitação pelo parser histórico, incluindo formato, regras de categorias/âmbito e citações literais, não verdade jurídica ou associação semanticamente correta ao alvo. As quatro rejeições IAedu não equivalem a quatro papéis errados; as 26 aceitações não equivalem a 26 anotações corretas ou prontas para treino.

A comparação usa as mesmas 30 menções segundo o relatório, preservando texto, entidade e offsets. A baseline v1 original foi identificada pelo raw e flags históricos conservados na revalidação; não se usam as 20 aceitações após recuperação de evidência como se fossem v1 original. Não foi aplicada nova recuperação ou alterado qualquer resultado histórico.

| Erro por registo, segundo o relatório | Qwen v1 original | Qwen v2 original | IAedu v2 original |
|---|---:|---:|---:|
| evidence_not_exact_short_substring | 21 | 22 | 3 |
| duplicate_role | 2 | 5 | 0 |
| scope_category_mismatch | 3 | 4 | 0 |
| invalid_role | 1 | 0 | 1 |

As categorias podem sobrepor-se. Os três problemas de citação e o campo other_roles não literal permanecem nos outputs originais, sem correções retroativas nem novas chamadas para melhorar a aceitação.

O relatório descreve 25 respostas supported e uma invalid_entity entre as 26 conformes. Uma abstenção por span inválido pode cumprir o protocolo sem produzir um papel utilizável para treino. Regista oito respostas UNKNOWN e nove atribuições em other_roles nos outputs conformes; estas propostas continuam pendentes de revisão. As sugestões qualitativas de melhor associação ao alvo e de âmbito são exploratórias, não métricas de exatidão adjudicadas.

## Identidade do serviço e limites

**Backend desconhecido.** “OpenAI GPT-5.5” é apenas a etiqueta apresentada/guardada pelo IAedu. Segundo o relatório, model_metadata_returned está vazio nos 30 registos e backend_model_identity_status é not_found_in_parsed_metadata. Não se confirmou modelo/checkpoint backend nem ausência de ferramentas/instruções adicionais. Não atribuir o resultado a pesos GPT-5.5 verificados.

O agente IAedu e Qwen local diferem na modalidade de entrega, configuração interna e controles possivelmente não expostos. O mesmo texto de prompt não isola todos esses fatores. Não se registam tempos completos ou parâmetros de geração não documentados como se tivessem sido medidos nesta revisão.

O relatório refere 30 threads distintas e coincidência de IDs/ordem/offsets e de hashes de previsões/resumos; não foram auditados aqui os corpos HTTP/eventos completos. Distinção documental/processual e elegibilidade continuam a depender dos manifestos privados e da proteção de origem, não da mera contagem de documentos distintos.

As 30 menções foram usadas para desenvolver o prompt e rever propostas. São desenvolvimento/calibração, não avaliação final independente. Todas mantêm human_validated=false, requires_review=true e elegibilidade de treino NOT_ESTABLISHED. Não calcular accuracy/F1, converter concordância em gold ou iniciar treino com base nesta conformidade.

## Decisões pendentes antes de estabilizar o protocolo

- **UNKNOWN versus insufficient:** distinguir pessoa válida sem papel principal sustentado de contexto incapaz de estabelecer o papel. Participação numa narrativa não prova estatuto processual; falta de prova na janela não prova ausência no processo inteiro. Não usar invalid_entity apenas por ignorância do papel.
- **Âmbito:** separar temporalidade, decisão anterior do mesmo processo e processo citado distinto. Não transferir um papel histórico para o processo atual nem escolher cited_proceeding apenas porque existe transcrição. Clarificar também a cobertura de AUTOR em ações laborais, sem alargar automaticamente a taxonomia.
- **REFERENCE:** adjudicar o suporte mínimo para autoria doutrinária nominal sem título de obra identificado. Não mudar a interpretação retrospectivamente para melhorar a taxa de aceitação.
- **other_roles:** decidir se se limitam a papéis jurídicos/processuais ou se incluem profissões, relações familiares e descrições narrativas. O prompt atual é amplo: não tratar automaticamente todas essas propostas como erros. Continuam exigidas designação literal e evidência ligada ao alvo; uma descrição construída pode falhar o parser independentemente de ser plausível.

As alternativas e possíveis citações corretivas permanecem sugestões, não labels gold. Qualquer adjudicação futura deve gerar protocolo/artefacto derivado versionado, preservando o raw e os resultados originais. A revisão humana de papéis, âmbito, spans e abstenção continua pendente.

Próxima etapa: [plano para 100 novas menções](../docs/experiment_19c_next100_plan.md), sem seleção, execução API ou autorização automática nesta tarefa.
