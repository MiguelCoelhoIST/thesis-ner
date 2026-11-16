# Experiência 19b — dimensão do corpus e inventário privado

> Enquadramento de 16-11-2026 — PLANEAMENTO histórico: 384 ocorrências recuperadas e extrapolações condicionais, sem NER integral nesta etapa. O job 15216 posterior concluiu os 191 textos, segundo confirmação do utilizador. Não repetir estes comandos históricos para preparar a 19c. Ver [estado atual](../docs/THESIS_STATE.md).

Planeamento local; sem LLM, transmissão, treino ou quotas por papel. O inventário conhecido é PARCIAL, não confundir com todas as menções.

## Conclusão

O universo de preparação passa a ser o corpus auditado inteiro: **191 conteúdos textuais distintos**, não os lotes de 40 ou 430 candidatos. São 15.102.124 caracteres e 2.411.871 palavras separadas por whitespace. Os 388 ficheiros incluem 197 versões textuais redundantes. O maior texto tem 1.024.075 caracteres.

**O total exato de menções PER ainda não pode ser recuperado dos artefactos existentes.** A auditoria guarda contagens e intervalos de janelas, não todas as entidades/offsets previstos. O cache era em memória. As janelas dependiam de âncoras e cobriam apenas 9.636.451 caracteres distintos (63,81%); faltavam 5.465.673 caracteres, 36,19%. Retirar apenas o limite de 60 por papel não resolve a cobertura.

Os 35.876 spans PER aceites registados na auditoria referem-se às 388 versões e apenas às janelas antigas. Não são 35.876 pessoas distintas nem a dimensão do futuro dataset. Não se pode dividir esse número por dois para obter uma contagem exata deduplicada.

## Reutilização e duplicados

Do pool de 430 recuperaram-se **384 ocorrências** por hash do documento e offsets documentais exatos; 46 linhas eram repetições dessa unidade. Nove ocorrências têm mais de um contexto legado distinto, que foi preservado no inventário parcial. As labels sugeridas não foram copiadas. A mesma grafia de pessoa em posições diferentes continua a ser composta por menções diferentes: o papel pode mudar.

Também existe um pequeno cache posterior de privacidade, no manifesto privado da exportação dos 40 exemplos: 40 contextos com 69 previsões PER, além de DAT/LOC/ORG/MOR. Há 29 spans PER brutos cujos offsets não coincidem com o subconjunto recuperado do pool. Não foram somados automaticamente às 384 menções aceites: são previsões de contextos recortados, sujeitas a validação de fronteiras/entidade e diferentes limites. Este cache pode ser reutilizado parcialmente após normalização/validação, mas não cobre o corpus e não substitui uma passagem completa.

O inventário conhecido é um **limite inferior de ocorrências já disponíveis**, não uma amostra a impor à anotação futura e não um dataset gold. O total final poderá diferir inclusive por variação das previsões quando muda a janela NER.

## Dimensão operacional estimada — não resultados medidos

Uma extrapolação meramente operacional dá aproximadamente **27 mil menções**: `35876 / (20096802 - 266614) * 15102124 = 27322`, usando a densidade de spans aceites por carácter coberto na auditoria antiga. Pressupõe que a densidade nas versões duplicadas, documentos únicos e regiões sem âncoras é semelhante; **essa hipótese não foi validada e pode estar errada**. Há viés lexical, multiplicidades diferentes de versões, variação de contexto NER e filtros automáticos. Não é previsão estatística, limite garantido ou intervalo de confiança.

Para planeamento, considerar cenários de 10/20/40 mil menções: 100/200/400 lotes de 100 por anotador LLM. O tamanho do lote será um limite de contexto/custo, **não uma redução do universo de exemplos**. Com até 800 caracteres de cada lado e uma hipótese de alvo de 30 caracteres, os contextos somariam aproximadamente 16,3/32,6/65,2 milhões de caracteres, antes de instruções/respostas. Esses valores JSON são aproximações condicionais, não máximos certificados. Dois LLMs duplicam aproximadamente o volume de anotação; custos monetários e tokenização dependem da ferramenta/configuração ainda não escolhida. Não foram consultadas APIs ou preços.

## Processos relacionados e leakage

Foram construídos **187 blocos conservadores** a partir dos 191 hashes e das raízes potenciais de todas as versões, incluindo aliases contraditórios. Não são 187 casos juridicamente independentes certificados. Onze documentos pertencem a componentes com várias raízes concorrentes; quatro não têm raiz reconhecida no componente. São 47 documentos sinalizados para revisão de identidade por conflito ou cardinalidade das raízes. Proveniências de fonte única continuam preservadas e não se tornam verificadas automaticamente.

IDs legados não verificados entram apenas como arestas conservadoras de bloqueio; não substituem cabeçalho ou filename, nem adjudicam a identidade. O manifesto conserva todas as evidências. Mesmo hash elimina a repetição textual, não resolve desacordos entre IDs exatos. Decisões/incidentais relacionados devem ficar no mesmo split. Referências no corpo não são promovidas a identidade nem toda a rede de citações é automaticamente fundida.

Onze documentos únicos estão em blocos relacionados com os documentos piloto e ficam assinalados para reserva/avaliação separada. Não houve correspondências nos grupos gold normalizáveis ou contenção literal dos contextos gold normalizados; três IDs gold não são interpretados pelo normalizador. Isto não certifica ausência de leakage. Antes dos splits, rever também citações, paráfrases e contextos repetidos entre grupos diferentes. O inventário pode descrever todo o corpus sem autorizar treino nos itens protegidos.

## Ficheiros preparados e fase ainda necessária

Versão canónica desta preparação, exclusivamente em `data/raw/`:

| Artefacto | Conteúdo |
| --- | --- |
| `experiment_19b_corpus_plan02_documents.jsonl` | 191 documentos canónicos, aliases, hashes, evidências de processo, blocos e reservas |
| `experiment_19b_corpus_plan02_known_mentions_PARTIAL.jsonl` | 384 ocorrências recuperadas, offsets, contexto, variantes e IDs legados privados |
| `experiment_19b_corpus_plan02_manifest.json` | Hashes dos inputs/scripts, parâmetros e contagens; total completo ainda null |
| `experiment_19b_corpus_plan02_task.json` | Instruções/schema para nove papéis mais REFERENCE experimental, SILVER, sem autorização de transmissão |

Uma tentativa de preparação anterior deixou dois ficheiros locais plan01 sem manifesto completo; não são a versão canónica e não foram apagados nem sobrescritos. Usar plan02.

O [preparador](../src/data/prepare_stj_corpus_inventory.py) é read-only relativamente ao corpus/artefactos antigos. Sem `--run-ner`, não carrega o modelo. Com essa opção, percorre por omissão **todos os 191 textos únicos**, sem âncoras ou quotas, usando janelas de 6000 caracteres com 600 de sobreposição: 2874 janelas e 16.711.924 caracteres de entrada incluindo sobreposição. Reutiliza `detect_person_spans(..., windows=...)`, `nlp.pipe`, o leitor documental e o modelo Eduardo existente.

A alteração mínima ao extrator é um callback opcional `prediction_sink`, sem mudar o comportamento padrão: permite persistir previsões de todas as classes NER e as janelas de origem. A futura execução escreve `*_ner_predictions.jsonl` e `*_mentions.jsonl`, além do manifesto. As previsões brutas conservam PER que os filtros rejeitaram e entidades úteis à privacidade, sem as promover a menções válidas. A filtragem conservadora pode falhar; a contagem resultante é de spans aceites pelo pipeline, não recall humano certificado. A execução completa **não foi iniciada**.

Cada menção tem ID estável por hash/offsets, ID de contexto separado, offsets no documento e no excerto, texto contínuo, alvo, proveniência/bloco, `label=null`, `human_validated=false`, `annotation_tier=UNANNOTATED`. Não há suggested_label. Repetições de nome em posições diferentes são mantidas. Uma ampliação de contexto mantém o ID da ocorrência e altera o ID do contexto. Os 800 caracteres de cada lado são configuráveis e não garantem suficiência; inferências longas e âmbito processual podem exigir contexto adicional.

## Comandos e separação da transmissão

Preparação já executada, sem NER; os outputs existentes não serão sobrescritos:

```powershell
.\venv\Scripts\python.exe src/data/prepare_stj_corpus_inventory.py `
  --input-dir data/raw/iris/naoanomimizados_txt
```

Para obter a contagem real, numa **alocação Slurm GPU autorizada**, com `venv-ner` e outputs novos, depois de confirmar recursos:

```bash
source venv-ner/bin/activate
python -u src/data/prepare_stj_corpus_inventory.py \
  --input-dir data/raw/iris/naoanomimizados_txt \
  --prefix data/raw/experiment_19b_corpus_fullNER01 \
  --report results/experiment_19b_corpus_fullNER01.md \
  --run-ner --gpu-id 0 --batch-size 4
```

Não executar fora de Slurm nem fixar GPU física 3. Um teste técnico pode usar `--max-documents 3` e outros nomes; fica explicitamente marcado como parcial e não limita a passagem final. Não foi submetido job nesta sessão. Não usar esta contagem de janelas como benchmark de tempo; é necessário medir o novo regime.

Depois: validar spans/inventário completo, rever grupos protegidos/ambíguos, preparar desidentificação local por documento e lotes, mapa privado de IDs/offsets, inspeção de privacidade e só então autorizar eventualmente a transmissão. O exportador antigo com default 40 e o validador de candidatos não são interfaces prontas para este novo inventário: reutilizar as funções de pseudonimização e adaptar a interface/validação sem inventar suggested_label. Não enviar os ficheiros privados acima.

As respostas por LLM devem registar modelo/configuração/prompt, labels propostas, evidência, scope, uncertain e parsing, sempre **SILVER e human_validated=false**. REFERENCE fica experimental, separada da taxonomia fina aprovada; não alterar automaticamente mapper ou regras de anonimização. Multi-label só quando sustentado para a mesma ocorrência; UNKNOWN não substitui contexto insuficiente. Concordância entre LLMs ou com palavras lexicais não é accuracy/F1 sem gold independente. Qwen permanece suspenso; esta preparação não fez anotação nem transmissão GPT/Claude.

## Validação

100 testes passaram, incluindo oito novos de deduplicação, aliases, hashes, cobertura de janelas, ocorrências/contextos distintos, callback e CLIs com modelo falso. Foram verificadas as 388 correspondências de hash/comprimento com os textos locais. Nenhum treino, dataset antigo ou benchmark foi alterado. Os testes sintéticos não provam desempenho/recall do inventário completo ainda não executado.

## Contagens legíveis por máquina

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
  "recovered_known_occurrences_lower_bound": 384,
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
