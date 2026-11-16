# Validação do exportador local — 40 exemplos

> Enquadramento de 16-11-2026 — Validação técnica histórica concluída da exportação de 40 exemplos. full01 refere-se ao lote de 40, NÃO ao corpus completo; sem anotação ou envio externo. Ver [estado atual](../docs/THESIS_STATE.md).

Desidentificação/pseudonimização assistida, NÃO anonimização certificada. Nada foi enviado.

Os 40 registos foram selecionados na ordem original. IDs opacos ligam-se aos originais apenas no mapa privado. Nenhuma sugestão lexical foi exportada.

```json
{
  "examples": 40,
  "redactions_by_kind": {
    "DADO": 300,
    "PESSOA": 70,
    "PROCESSO": 13,
    "LOCAL": 17,
    "DATA": 18,
    "ORGANIZACAO": 14,
    "MORADA": 1
  },
  "offset_checks_passed": 40,
  "reversible_text_checks_passed": 40,
  "role_anchor_count_changes": 0,
  "records_with_role_anchor_changes": 0,
  "courtesy_title_boundary_adjustments": 2,
  "residual_direct_identifier_matches": {
    "EMAIL": 0,
    "URL": 0,
    "PROCESSO": 0,
    "IBAN": 0,
    "CONTACTO": 0,
    "DATA": 0,
    "MATRICULA": 0
  },
  "residual_unclassified_capitalized_tokens": 1,
  "human_privacy_review_required": true,
  "anonymization_certified": false,
  "original_ids_exported": false,
  "input_unchanged": true,
  "input_sha256": "6a392e6c2215f2faaa4ceee30ec8da0085016e2291a3f9043c8704404d998b05"
}
```

Inspecionar nomes residuais/aliases, moradas, contactos, processos, datas, entidades, factos raros e combinações reidentificantes. Alterações de contagem de âncoras podem indicar perda de contexto: rever antes de partilhar. NER/regex não garantem ausência de dados pessoais.

## Verificações complementares

- 92 testes passaram, incluindo cobertura sintética dos 40 registos, associação por ID, procura de identificadores residuais e títulos de tratamento repetidos.
- JSONL com exatamente 40 IDs externos únicos, na ordem original; o manifesto conserva os 40 IDs internos e registos originais. Verificadas igualdade dos registos-fonte, reconstrução dos textos, offsets e reintegração dos 40 IDs.
- Whitelist do JSONL verificada: sem suggested_label, caminhos-fonte, IDs processuais ou registos originais nos metadados exportados. Alvos transformados identificados por offsets exatos e markers canónicos.
- Os cinco primeiros exemplos transformados coincidem com o piloto anterior, que não foi alterado. Hashes do lote, pool v5, revisões humanas e benchmark congelado permanecem inalterados.
- JSONL, tarefa/schema e manifesto privado confirmados como ignorados pelo Git. Nenhum dado foi enviado, anotado ou usado para treino; Qwen continua suspenso.

## Alertas que exigem atenção antes de partilhar

O único alerta automático de capitalização foi analisado sem publicar o texto: em EXEMPLO_018, o token é composto exclusivamente por pseudónimos gerados concatenados. Não é uma nova evidência de nome residual, mas recomenda-se inspeção da legibilidade. O alerta bruto permanece registado, sem o apagar silenciosamente.

As duas normalizações de fronteira correspondem a títulos de tratamento em spans PER: preservaram o título e o alvo exato, registando no manifesto os spans NER originais e os limites de ocultação. Nenhum nome foi aparado nem se inventaram offsets do candidato original. Outras sobreposições continuam a falhar de forma explícita.

Apesar de zero correspondências dos padrões diretos, a pseudonimização reversível **não garante anonimização**: nomes não reconhecidos, aliases, factos raros, profissões/relações e combinações de contexto podem identificar pessoas. Contagens de âncoras preservadas não garantem que todas as pistas jurídicas sobreviveram. Rever o JSONL antes da partilha e nunca enviar o manifesto privado. Ver [instruções](../docs/external_annotation_export.md).
