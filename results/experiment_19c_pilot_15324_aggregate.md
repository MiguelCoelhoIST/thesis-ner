# Experiência 19c — agregado do piloto 15324

Data do registo 18-11-2026. Fonte: valores declarados no patch fornecido pelo utilizador, atribuídos nele às saídas de terminal e campos do `run.json`. Os logs e artefactos privados completos estão no INESC e não foram verificados neste workspace. Este registo conserva apenas agregados declarados, sem certificar uma execução local/remota nesta revisão.

O preflight 15323 terminou com `COMPLETED`, exit `0:0` e `status=preflight_passed`. O piloto 15324 terminou com `completed_with_invalid_outputs`, exit `1:0` e todos os 30 registos persistidos.

| Medida | Valor comunicado |
| --- | --- |
| Modelo | Qwen/Qwen3-8B |
| Revisão | b968826d9c46dd6066d109eabc6255188de91218 |
| Prompt | 19c-v1 |
| GPU | Quadro RTX 6000, 24 GB |
| Dtype | float16 |
| Python / Torch / Transformers | 3.11.15 / 2.11.0+cu130 / 4.53.2 |
| Duração do piloto | 156,216 segundos |
| Registos | 30 |
| Outputs válidos pelo protocolo | 8 |
| Outputs inválidos | 22 |
| Registos com erro de evidência | 21 |
| Registos com duplicate_role | 2 |
| Registos com scope_category_mismatch | 3 |
| Registos com invalid_role | 1 |
| Human validated | false |

As categorias de erro podem coexistir num registo. O diagnóstico posterior do utilizador contou 26 excertos de evidência rejeitados, dos quais 10 continham marcadores, 1 excedia 240 caracteres e 21 coincidiam com o contexto após remover marcadores e normalizar whitespace. As três últimas contagens sobrepõem-se e referem excertos.

O quociente 8/30 mede conformidade com o protocolo. A correção dos papéis exige revisão humana independente. A preparação de recuperação offline está documentada em [19c](../docs/experiment_19c_qwen_pilot.md); a contagem real após recuperação continua pendente. A coorte é exploratória, com elegibilidade de treino por estabelecer.
