# Validação do exportador local — piloto externo de cinco exemplos

> Enquadramento de 16-11-2026 — Validação técnica histórica concluída de cinco exemplos exportados localmente; sem anotação ou envio externo. Não certifica anonimização. Ver [estado atual](../docs/THESIS_STATE.md).

Desidentificação/pseudonimização assistida, NÃO anonimização certificada. Nada foi enviado.

Os cinco primeiros registos foram selecionados na ordem original. IDs opacos ligam-se aos originais apenas no mapa privado. Nenhuma sugestão lexical foi exportada.

```json
{
  "examples": 5,
  "redactions_by_kind": {
    "DADO": 31,
    "PESSOA": 7,
    "PROCESSO": 1,
    "LOCAL": 2,
    "DATA": 1
  },
  "offset_checks_passed": 5,
  "reversible_text_checks_passed": 5,
  "role_anchor_count_changes": 0,
  "human_privacy_review_required": true,
  "anonymization_certified": false,
  "original_ids_exported": false,
  "input_unchanged": true,
  "input_sha256": "6a392e6c2215f2faaa4ceee30ec8da0085016e2291a3f9043c8704404d998b05"
}
```

Inspecionar nomes residuais/aliases, moradas, contactos, processos, datas, entidades, factos raros e combinações reidentificantes. Alterações de contagem de âncoras podem indicar perda de contexto: rever antes de partilhar. NER/regex não garantem ausência de dados pessoais.

## Verificações complementares executadas

- 89 testes passaram, incluindo oito testes novos exclusivamente sintéticos do exportador.
- O JSONL tem cinco registos e corresponde aos cinco primeiros IDs originais, na ordem original; a associação por IDs externos foi conferida contra o mapa privado.
- Whitelist dos campos exportados verificada: não contém proveniência, IDs internos, registos originais ou suggested_label. O mapa retém essas informações apenas localmente.
- Conferidos os hashes do lote original, pool v5, dez revisões piloto e benchmark congelado: todos inalterados.
- Lote transformado, tarefa/schema e mapa privado confirmados como ignorados pelo Git. Não houve envio externo, treino, execução Qwen ou commit.
- Após transformação, os detetores de email, URL, processo, IBAN, contacto, data numérica e matrícula encontraram zero correspondências. Esta é uma verificação limitada dos padrões implementados, não uma certificação de ausência de identificadores ou de anonimização; números estatutários podem permanecer deliberadamente.

O ficheiro transformado está pronto para **inspeção local**, não automaticamente aprovado para partilha. Consultar [instruções e limitações](../docs/external_annotation_export.md). Nunca partilhar o ficheiro `private_map` nem os dados originais.
