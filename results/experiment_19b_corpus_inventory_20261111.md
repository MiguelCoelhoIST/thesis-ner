# Experiência 19b — dimensão do corpus e inventário privado

> Enquadramento de 16-11-2026 — RECUPERAÇÃO PARCIAL histórica de 412 ocorrências, não o inventário integral. O job 15216 posterior concluiu os 191 textos, segundo confirmação do utilizador. Os próximos passos/comandos abaixo são históricos. Ver [estado atual](../docs/THESIS_STATE.md).

**Verificação em 11-11-2026.** Recuperação local, sem nova inferência NER, LLM, transmissão, treino ou quotas por papel. O inventário conhecido é PARCIAL, não confundir com todas as menções.

## Resultado confirmado e limite da recuperação

| Unidade | Contagem |
| --- | ---: |
| Documentos-ficheiro auditados e hashes conferidos | 388 |
| Conteúdos textuais únicos | 191 |
| Versões redundantes por conteúdo | 197 |
| Caracteres nos textos únicos | 15.102.124 |
| Palavras por whitespace | 2.411.871 |
| Blocos processuais conservadores, não independência certificada | 187 |
| Documentos sinalizados para revisão de identidade | 47 |
| Ocorrências únicas recuperadas do pool 19a | 384 |
| Ocorrências adicionais recuperadas do cache de privacidade | 28 |
| Inventário recuperado atual | **412 ocorrências, em 187 conteúdos únicos** |
| Ocorrências com variantes de contexto legado preservadas | 9 |
| Total exato de PER no corpus completo | **Desconhecido — não está guardado** |

Os 430 candidatos antigos não são o limite do universo. Contêm 46 linhas redundantes da mesma ocorrência, após agrupar por hash do texto e offsets, resultando em 384 unidades. A recuperação adicional não se baseou em nomes capitalizados nem em âncoras: reutilizou previsões PER já guardadas pelo Eduardo. Nomes iguais em posições diferentes continuam a ser menções diferentes; alterar/ampliar o contexto mantém o ID da ocorrência e cria outro context_id. Nenhuma proposta jurídica foi produzida.

### Onde estavam as deteções

- A auditoria 19a regista 35.876 PER aceites, mas não guarda todas as entidades/offsets. São contagens sobre 388 versões e janelas lexicais, não pessoas únicas nem o futuro tamanho do dataset. O cache desse extrator era apenas em memória.
- Os intervalos antigos cobriam 9.636.451 caracteres únicos (**63,81%**). Ficaram 5.465.673 caracteres fora dessas janelas. Mesmo nos 63,81% processados, as previsões completas não foram persistidas: não basta executar apenas os restantes 36,19%.
- O manifesto privado da exportação de 40 exemplos guardou 69 PER locais: 40 coincidem com ocorrências já conhecidas, 28 são novas e compatíveis com os offsets existentes e uma é variante sobreposta, conservada no ficheiro de revisão sem inventar uma segunda ocorrência. O conteúdo local foi confrontado com o texto-fonte antes da projeção dos offsets.
- A procura em `data/raw/` não encontrou ficheiros completos de previsões NER nem manifestos de inventário completo. Um DocBin adicional foi inspecionado sem executar NER: 5.659 documentos, 1.325.186 caracteres, **zero correspondências exatas por hash com os 191 textos**. Sem alinhamento/proveniência confirmados, não foi incorporado. Não se executou pickle nem se confundiram dados de outro corpus/fragmentos com estes acórdãos.

**Não é possível obter honestamente o inventário completo sem nova passagem NER.** O código já a suporta sobre todos os textos distintos, sem limites por papel e sem âncoras. Não foi executada nesta fase, nem submetido job: a execução remota continua sujeita a alocação Slurm/autorização. Recuperar o que existe não justifica certificar cobertura que os ficheiros não contêm.

## Cobertura de UNKNOWN e REFERENCE

Os 412 contextos recuperados ainda contêm alguma âncora lexical dos oito papéis: são provenientes de uma descoberta originalmente enviesada por essas âncoras. Isso não significa que o alvo tenha esse papel; a âncora pode referir-se a outra pessoa. Este inventário recuperado não demonstra cobertura suficiente de UNKNOWN/REFERENCE ou de ocorrências sem pistas lexicais.

A passagem integral usa janelas que cobrem todo o texto, independentemente de âncoras. O Eduardo ainda pode omitir pessoas, autores bibliográficos ou confundir outros tipos de entidade. Os filtros conservadores, incluindo rejeição de coordenações, podem excluir apelidos legítimos com “e”; não são validação jurídica. Por isso ficam previstas duas saídas: todas as previsões brutas com proveniência das janelas e as menções aceites automaticamente. As rejeitadas devem ser auditáveis, não desaparecer silenciosamente.

O output completo significará cobertura de processamento dos 191 textos, não recall humano perfeito. UNKNOWN é pessoa válida sem papel-alvo suportado, nunca sinónimo de processo sem ID, ambiguidade ou span errado. REFERENCE continua experimental e distinta de AUTOR processual e de regras de anonimização. A interface admite multi-label sustentado e âmbito por label; contexto insuficiente deve produzir incerteza, não labels forçadas.

## Proveniência, duplicados e leakage

O manifesto documental conserva todas as versões por hash, IDs exatos e evidências de cabeçalho/filename/referências, sem corrigir conflitos. São 11 textos em componentes com raízes concorrentes e quatro sem raiz de componente reconhecida. Os 187 blocos são agrupamentos conservadores; não equivalem a 187 processos independentes certificados. IDs legados são evidência não verificada usada apenas para bloquear co-seleção/splits potencialmente inseguros.

Onze textos pertencem a blocos relacionados com o piloto. As comparações disponíveis não encontraram sobreposição nos grupos gold normalizáveis ou contenção literal dos excertos gold; três IDs gold não são interpretados pelo normalizador. Isso não exclui aliases, citações, paráfrases ou outros vínculos. Não foi criado qualquer split de treino/avaliação.

Os planos dos 412 itens separam coortes: 20 reservados por relação com o piloto, 101 com revisão de identidade requerida e 291 sem atribuição de split. Não se excluiu nenhum item da preparação. **Lotes não são splits**: um bloco pode ocupar vários lotes, mas deverá permanecer inteiro num futuro split, incluindo na comparação fina/agregada. Contextos repetidos/citados entre blocos exigem revisão adicional.

## Ficheiros produzidos, todos privados exceto este relatório

Prefixo: `data/raw/experiment_19b_corpus_recovered_20261111_v1_`.

| Sufixo | Conteúdo |
| --- | --- |
| `documents.jsonl` | 191 textos canónicos, todas as versões/evidências e blocos |
| `known_mentions_PARTIAL.jsonl` | 412 ocorrências sem suggested_label, com offsets/contextos e estado UNANNOTATED |
| `cached_span_review_PRIVATE.jsonl` | 69 previsões PER recuperadas e decisão técnica de reutilização/revisão |
| `manifest.json` | Hashes dos inputs/scripts, parâmetros, contagens; inventory_complete=false |
| `task.json` | Instruções/schema para papéis finos e REFERENCE; respostas sempre SILVER, nunca human-validated |

Planos privados: `data/raw/experiment_19b_batches_RECOVERED_PARTIAL_20261111_v1/`, com seis ficheiros de IDs e um manifesto. São descritores sem textos prontos para partilha. Não foram anotados, enviados, pseudonimizados novamente ou aprovados para divulgação. Não reutilizar a exportação antiga de 40 como se representasse o corpus completo.

A infraestrutura anterior foi ampliada de forma localizada: o preparador aceita `--reuse-privacy-map`; o novo [planeador de lotes](../src/annotation/plan_inventory_batches.py) inclui todos os IDs e recusa inventários parciais salvo reconhecimento explícito com `--allow-partial`. Não se atribuem labels por sugestão lexical, não se anotam papéis com regex nem se treinam modelos.

## Dimensão esperada

Os 412 contextos atuais somam **623.274 caracteres**, com máximo de 1.640 por contexto. A contagem refere-se ao excerto antes de desidentificação e não inclui instruções, JSON ou respostas.

O total futuro só será medido na passagem NER integral. A extrapolação antiga de cerca de **27 mil menções** permanece uma hipótese operacional fraca: pressupõe densidade semelhante em versões duplicadas, textos únicos e regiões com/sem âncoras. Não é medição, limite garantido ou intervalo estatístico. Para planeamento, 10/20/40 mil menções significam aproximadamente 100/200/400 lotes de 100 por LLM, antes de separações por reserva/proveniência. Dois anotadores LLM duplicam o número de respostas esperado. O limite de lote deve depois ser ajustado à tokenização e contexto da ferramenta; 100 registos não garante que caibam numa chamada.

## Próximo comando e sequência correta

**Não há ainda material completo legitimamente pronto para enviar a um LLM externo.** O próximo passo obrigatório para todo o corpus é obter as previsões que faltam, não começar uma anotação de 412 itens afirmando que são todos.

Num ambiente `venv-ner` e numa alocação Slurm autorizada, começar com um teste técnico curto de cobertura integral por documento, sem definir a futura amostra SILVER:

```bash
source venv-ner/bin/activate
python -u src/data/prepare_stj_corpus_inventory.py \
  --input-dir data/raw/iris/naoanomimizados_txt \
  --prefix data/raw/experiment_19b_inventory_smoke_20261111_v1 \
  --report results/experiment_19b_inventory_smoke_20261111_v1.md \
  --run-ner --gpu-id 0 --batch-size 4 --max-documents 3
```

Depois de validar o teste, repetir com novos nomes `experiment_19b_inventory_full_20261111_v1` e **sem `--max-documents`**, processando os 191 textos. Não fixar GPU física 3, instalar pacotes, descarregar pesos ou submeter jobs sem confirmação. Qwen permanece suspenso. Esses comandos não foram executados nesta sessão.

Quando o inventário integral estiver validado, o próximo comando de preparação de lotes é:

```bash
python src/annotation/plan_inventory_batches.py \
  --input data/raw/experiment_19b_inventory_full_20261111_v1_mentions.jsonl \
  --inventory-manifest data/raw/experiment_19b_inventory_full_20261111_v1_manifest.json \
  --output-dir data/raw/experiment_19b_batches_full_20261111_v1 \
  --batch-size 100
```

Não usar `--allow-partial` para apresentar lotes recuperados como corpus completo. A chamada já realizada com essa opção serviu apenas para produzir planos dos 412 itens disponíveis, com status parcial explícito.

Depois: exportar contextos desidentificados com mapa privado, sem IDs processuais/nomes/caminhos-fonte ou suggested_label no material do anotador; inspecionar privacidade e contexto; obter autorização de transferência antes de enviar. Reutilizar as funções do exportador anterior, não o seu limite/validador de candidatos de 40. O cache futuro de todas as classes NER deve ajudar a evitar executar NER novamente só para a desidentificação. Pseudonimização reversível não garante anonimização; factos raros e relações podem identificar pessoas.

Respostas GPT/Claude serão guardadas separadamente com modelo, prompt/versão, evidência, âmbito, incerteza e parsing, como SILVER e human_validated=false. Concordância entre modelos não é gold nem accuracy/F1 sem avaliação independente. Não há resultados de anotação desta sessão.

## Verificação desta sessão

106 testes passaram, incluindo recuperação de spans guardados, conflitos/alteração de contexto, cobertura sem âncoras e planeamento de todos os 257 IDs num caso sintético. As 388 fontes foram relidas e confrontadas com os hashes da auditoria. Os offsets e contexto das 412 ocorrências, IDs únicos e associação aos documentos foram verificados. Benchmarks, revisões, datasets e resultados anteriores foram preservados. Nenhuma API, SSH, download, treino, nova inferência NER, anotação LLM ou commit foi executado.

Fontes: [estado](../docs/THESIS_STATE.md), [decisões](../docs/DECISIONS.md), [protocolo 19a](../docs/experiment_19a_annotation_protocol.md), [planeamento anterior](experiment_19b_corpus_plan02.md), [preparador](../src/data/prepare_stj_corpus_inventory.py), [exportador](../src/annotation/export_external_annotation.py) e inputs privados identificados por hash no novo manifesto.

## Contagens da execução local

```json
{
  "audited_documents": 388,
  "unique_texts": 191,
  "duplicate_text_versions": 197,
  "unique_text_characters": 15102124,
  "unique_text_words_whitespace": 2411871,
  "largest_document_characters": 1024075,
  "split_blocks_conservative": 187,
  "documents_requiring_identity_review": 47,
  "documents_in_multi_root_blocks": 11,
  "documents_without_component_root": 4,
  "old_covered_unique_characters": 9636451,
  "old_accepted_PER_across_duplicate_versions_NOT_unique": 35876,
  "recovered_known_occurrences_lower_bound": 412,
  "recovered_from_19a_only": 384,
  "reused_privacy_cache_summary": [
    {
      "saved_PER_predictions": 69,
      "new_cached_occurrences": 28,
      "recovery_status_counts": {
        "exact_existing_occurrence": 40,
        "new_cached_PER_occurrence": 28,
        "overlapping_variant_needs_review": 1
      }
    }
  ],
  "legacy_duplicate_occurrence_records": 46,
  "known_occurrences_with_multiple_contexts": 9,
  "total_PER_mentions_complete": null,
  "planned_full_coverage_windows_6000_overlap_600": 2874,
  "planned_NER_input_characters_including_overlap": 16711924,
  "pilot_related_unique_documents": 11,
  "gold_known_process_overlap_documents": 0,
  "gold_context_containment_documents": 0,
  "gold_process_ids_not_normalized": 3,
  "NER_executed": false,
  "LLM_calls": 0,
  "inventory_complete": false,
  "dimension_scenarios_NOT_estimates": {
    "10000": {
      "annotation_rows_per_LLM": 10000,
      "batches_at_100_per_batch": 100,
      "maximum_context_characters_approx": 16300000
    },
    "20000": {
      "annotation_rows_per_LLM": 20000,
      "batches_at_100_per_batch": 200,
      "maximum_context_characters_approx": 32600000
    },
    "40000": {
      "annotation_rows_per_LLM": 40000,
      "batches_at_100_per_batch": 400,
      "maximum_context_characters_approx": 65200000
    }
  }
}
```
