## Conclusions — Role classification approaches

Three different approaches were explored for legal role classification:

### 1. Logistic Regression (baseline)
A simple bag-of-words classifier was used as an initial approach.

Observations:
- Works well for simple and direct patterns
- Fails in more complex sentences with multiple entities
- Cannot capture semantic meaning (e.g. synonyms or indirect expressions)
- Sensitive to vocabulary seen during training

Conclusion:
This approach is limited due to its reliance on surface-level lexical features.


### 2. Rule-based classifier
A rule-based system was implemented using keyword matching near the target entity.

Observations:
- Strong performance when explicit role keywords are present
- Highly interpretable and deterministic
- Achieves high accuracy on controlled datasets

Limitations:
- Depends on exact lexical patterns (e.g. "testemunha" vs "testemunho")
- Struggles with semantic variations and implicit roles
- Requires manual rule engineering

Conclusion:
The rule-based approach provides a strong baseline, but lacks flexibility and generalization.


### 3. Entity-aware rule-based classifier (best current baseline)

An improved version was implemented using:
- entity marking ([ENTITY] ... [/ENTITY])
- local pattern matching around the entity

Results:
- Achieved ~94% accuracy on realistic evaluation
- Correctly handles multiple entities in the same sentence
- Outperforms simple ML baseline in controlled scenarios

Limitations:
- Still fails in semantically indirect cases
- Example:
  "testemunho de Luís Matos" → should be TESTEMUNHA but predicted UNKNOWN

Conclusion:
This approach is highly effective when roles are explicitly stated near the entity, 
but fails when deeper semantic understanding is required.


### Final insight

There is a clear trade-off:

- Rule-based → high precision, low flexibility
- ML (simple) → flexible, but weak understanding
- Transformer (next step) → expected to combine both

This motivates the exploration of transformer-based models for better semantic understanding and generalization.