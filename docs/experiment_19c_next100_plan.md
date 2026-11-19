# 19c — preparação futura de 100 novas menções elegíveis

Plano documental de 19-11-2026. Nenhuma seleção de 100, chamada LLM, transferência ou treino foi executado nesta tarefa. O [agregado do piloto](../results/experiment_19c_iaedu_vs_qwen_aggregate.md) regista conformidade 26/30 no IAedu; não estabelece accuracy, backend identificado ou elegibilidade automática para treino.

Atualização posterior no mesmo dia: [prompt v3 e auditoria source-bound de capacidade](experiment_19c_v3_preparation.md) implementados/testados offline. Usar o novo comando de auditoria com as reservas dos 30 antes de selecionar; o comando genérico abaixo continua apenas um planeador. O inventário completo não está disponível neste workspace e a contagem real de elegíveis continua pendente no g09.

Atualização após execução comunicada pelo utilizador: auditoria com 3.033 menções, 64 grupos e zero pendências. A quota de 100 abaixo fica substituída por **até 64, uma por grupo**. Preparados [seletor/exportador e runner v3 de tamanho efetivo](experiment_19c_v3_batch.md); nenhuma nova anotação executada. O restante documento conserva o plano anterior, não o comando atual de preparação.

## Passos por ordem

1. **Conservar e rever o piloto:** manter raw, eventos, previsões, pedidos, autorização e manifestos privados dos 30. Resolver/versionar as decisões UNKNOWN/insufficient, âmbito temporal/processual, REFERENCE sem título e alcance de other_roles com os responsáveis metodológicos. Enquanto pendentes, conservá-las como hipóteses e não corrigir silenciosamente labels/metrics. Não repetir chamadas só para corrigir espaços nas citações. Preparação de proveniência pode avançar em paralelo, sem antecipar decisões semânticas.
2. **Reutilizar o inventário completo 19b:** 24.467 ocorrências PER de 191 textos distintos, segundo o estado confirmado do projeto. Usar os mentions/manifest/documents/ner_predictions e fontes originais do job 15216. Reutilizar load_bound_inventory e validate_document_sources de plan_inventory_batches.py; não repetir NER nem usar os candidatos amostrados 19a como universo. Validar IDs únicos, hashes, spans e contexto original.
3. **Inventariar reservas, sem assumir checks negativos:** usar plan_batches/review_reasons para grupos e pendências; depois group_index/assess_protection de prepare_stj_pilot_19c.py para revalidar positivamente as referências protegidas e a evidência privada de adjudicação. Os checks not_requested/null do inventário original continuam pendentes, não são ausência de overlap.
4. **Excluir o que já foi usado:** além do Gold50 e do piloto humano/fontes protegidas, reservar os 30 casos de desenvolvimento 19c e os seus documentos, hashes/duplicados, aliases e famílias/blocos de processo conhecidos. Essas 30 menções já orientaram o prompt. Fazer a exclusão por identidade/contexto/grupo, não só por ID de menção ou pelo nome da entidade. Não reutilizar labels IAedu/Qwen como prova independente de elegibilidade ou sementes gold.
5. **Contar primeiro o que sobra:** documentar ocorrências, documentos textualmente distintos e grupos elegíveis, conflitos, grupos desconhecidos, exclusões e motivos. Usar a política conservadora de proveniência existente; não corrigir IDs por suposição nem promover unresolved a seguro. Elegível para anotação exploratória não significa liberado para treino/eval ou transmissão externa.
6. **Selecionar sem forçar quota:** seed explícita (a seed 42 existente pode ser mantida), IDs novos, deduplicação de contextos e diversidade de PER/pseudónimos, múltiplas pessoas, citações, pistas e ausência de pistas. Flags lexicais servem a variedade, nunca labels verdadeiras. Incluir candidatos a UNKNOWN/REFERENCE sem os pré-rotular. Preservar ocorrências cujo contexto/papel muda e registar spans suspeitos sem alterar offsets originais.
7. **Fixar a unidade por processo:** preferir diversidade de grupos; se não houver 100 grupos disponíveis após as reservas, não inventar independência nem relaxar exclusões. Para obter 100 menções de menos grupos, é necessária decisão explícita sobre teto por grupo/contexto e uso apenas de desenvolvimento. Alternativamente, preparar um lote menor. Todas as menções de uma família ficam no mesmo split futuro. Relatar o número real de grupos, não apresentar 100 menções como 100 processos independentes.
8. **Congelar uma seleção nova:** registar método/seed, 100 IDs se viável, contexto/offsets, hashes, documentos/grupos, exclusões e evidência de proteção num manifesto privado novo. Reservar antecipadamente os grupos da futura avaliação independente. Não transformar a coorte de desenvolvimento em benchmark gold. Auditar uma amostra variada de casos fáceis/difíceis, não apenas respostas inválidas ou discordâncias entre modelos.
9. **Preparar pedidos e autorização próprios:** reutilizar a construção de mensagens v2, o parser histórico e a persistência/retoma do IAedu como componentes. Se a adjudicação exigir mudar protocolo/prompt, criar versão nova antes de gerar pedidos e documentar a diferença. Não incluir propostas, revisões ou suggested_label no input. Gerar cápsula/manifestos e autorização privada específicos para o lote novo, após revisão de privacidade. A autorização do piloto de 30 não é autorização de 100.
10. **Executar apenas numa etapa posterior:** só após seleção/integridade/protocolo/privacidade aprovados e capacidade do código adaptada/testada para 100. Manter SILVER, revisão pendente e backend desconhecido enquanto a API não o identificar. Decidir uso para treino apenas depois de controlo semântico e de splits; a conformidade não o autoriza.

## Capacidades existentes e limite que não se deve contornar

| Componente existente | Reutilização | Limite atual |
|---|---|---|
| plan_inventory_batches.py | Validação do inventário completo, grupos/aliases/pendências e planos de IDs com batch-size 100. | Não é seletor de 100 elegíveis: inclui coortes reservadas/review_required e não cria texto partilhável nem splits. |
| prepare_stj_pilot_19c.py | group_index, assess_protection, semelhança de conteúdo e seleção determinística. | A função select_pilot aceita count; o CLI usa 30 e não tem --count 100. A política atual usa no máximo um caso por grupo. Não acrescentar grupos insuficientes por suposição. |
| prepare_second_llm_pilot_19c.py | Mensagens cegas, preservação de offsets, manifestos e ficheiros individuais. | Usa load_pilot e o contrato histórico de exatamente 30. |
| portable_iaedu_pilot_19c.py / run_iaedu_pilot_19c.py | Cápsula, hashes, autorização, UUID por pedido, checkpoints, retoma e parser sem reparação. | Contrato de 30, nomes de ficheiros/faixas e autorização STJ_19C_30_IAEDU_API fixos. Não aceitam --batch-size 100 e não devem ser usados com um input truncado/forjado. |

Portanto, os scripts existentes permitem começar **a auditoria e o planeamento**; não se afirma que já exista execução de 100 pronta. Uma adaptação mínima/versionada de seleção e contratos de lote será necessária depois de apurar capacidade e política. Preservar os executáveis/checkpoints históricos do piloto e as suas verificações de código. Não editar hashes, manifests ou autorização para fazer os scripts de 30 aceitar 100.

## Próximo comando concreto — plano privado, não seleção elegível

No g09, com o código atualizado e venv-ner ativo, escolher um diretório novo:

```bash
python -u src/annotation/plan_inventory_batches.py \
  --input data/raw/experiment_19b_ner_full_15216_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_ner_full_15216_manifest.json \
  --batch-size 100 \
  --output-dir data/raw/experiment_19c_next100_inventory_plan01
```

Este comando valida o bundle e escreve planos privados de IDs/contagens; não executa NER/LLM nem envia contextos. Não escolher automaticamente batch_0001: analisar primeiro cohort/review_reasons e cruzar as reservas de Gold50, piloto humano e 30 de desenvolvimento. Os checks originais incompletos podem colocar todas as menções em reference_review_required; isso exige a revalidação explícita, não eliminar o flag. O número final disponível só pode ser afirmado após essa auditoria no corpus privado.

O passo seguinte é produzir o relatório de exclusões/capacidade de grupos usando as funções existentes e evidências privadas, com zero chamadas LLM. A seleção e execução do lote permanecem posteriores; esta tarefa só versiona documentação/agregados sem pessoas, textos ou identificadores privados.
