"""Bound actual Transformer WordPieces without truncating original text.

spaCy striding counts linguistic tokens, not BERT positions. Keep the trained
span getter, validate its exact strings (including special tokens), and refine
only unsafe outer character windows. No model/tokenizer files are modified.

Refined windows overlap by up to 600 characters (reduced for very small inputs).
They use source slices, never decoded WordPieces, so offsets remain exact.
NER predictions may change with context; this guarantees input coverage and
position safety, not perfect entity recall. Existing conservative reconciliation
and the inventory's complete raw prediction/provenance output remain in place.
"""


class TransformerLengthGuard:
    def __init__(self, get_spans, tokenizer, limit):
        self.original = get_spans
        self.tokenizer = tokenizer
        self.limit = limit
        self.maximum_checked = 0

    def maximum_wordpieces(self, docs):
        nested = self.original(docs)
        texts = [span.text for spans in nested for span in spans]
        if not texts:
            return nested, 0
        encoded = self.tokenizer(texts, add_special_tokens=True, padding=False,
                                 truncation=False, return_attention_mask=False,
                                 return_token_type_ids=False)
        maximum = max(map(len, encoded['input_ids']), default=0)
        return nested, maximum

    def __call__(self, docs):
        spans, maximum = self.maximum_wordpieces(docs)
        if maximum > self.limit:
            raise ValueError(f'Transformer input has {maximum} WordPieces including special tokens; limit {self.limit}. Refine outer windows; truncation is forbidden.')
        self.maximum_checked = max(self.maximum_checked, maximum)
        return spans


def get_length_guard(nlp):
    if 'transformer' not in getattr(nlp, 'pipe_names', ()):
        return None
    getter = nlp.get_pipe('transformer').model.attrs['get_spans']
    return getter if isinstance(getter, TransformerLengthGuard) else None


def install_length_guard(nlp):
    if 'transformer' not in nlp.pipe_names:
        return None
    model = nlp.get_pipe('transformer').model
    original = model.attrs['get_spans']
    if isinstance(original, TransformerLengthGuard):
        return {'effective_limit': original.limit, 'already_installed': True}
    tokenizer = model.tokenizer
    hf_model = model.transformer
    configured = int(hf_model.config.max_position_embeddings)
    declared = int(tokenizer.model_max_length)
    embeddings = getattr(getattr(hf_model, 'base_model', hf_model), 'embeddings', None)
    rows = getattr(getattr(embeddings, 'position_embeddings', None), 'num_embeddings', configured)
    limits = [int(value) for value in (configured, declared, rows) if int(value) > 0]
    limit = min(limits)
    special = tokenizer.num_special_tokens_to_add(pair=False)
    if limit <= special:
        raise ValueError('Transformer position limit leaves no room for text tokens')
    model.attrs['get_spans'] = TransformerLengthGuard(original, tokenizer, limit)
    return {'effective_limit': limit, 'model_max_position_embeddings': configured,
            'position_embedding_rows': int(rows), 'tokenizer_declared_model_max_length': declared,
            'special_tokens_per_sequence': special, 'truncation': False,
            'trained_span_getter': getattr(getattr(original, 'func', original), '__name__', type(original).__name__),
            'trained_span_parameters': getattr(original, 'keywords', {}),
            'policy': 'validate_internal_wordpieces_and_refine_unsafe_outer_windows'}


def refine_transformer_windows(text, nlp, windows, overlap_chars=600):
    guard = get_length_guard(nlp)
    report = {'validated': guard is not None, 'requested_windows': len(windows),
              'subdivisions': 0, 'maximum_original_wordpieces': 0,
              'maximum_safe_wordpieces': 0, 'effective_limit': guard.limit if guard else None}
    if guard is None:
        return list(windows), report
    safe = []
    for left, right in windows:
        pending = [(left, right, True)]
        while pending:
            a, b, initial = pending.pop()
            _, maximum = guard.maximum_wordpieces([nlp.make_doc(text[a:b])])
            if initial:
                report['maximum_original_wordpieces'] = max(report['maximum_original_wordpieces'], maximum)
            if maximum <= guard.limit:
                safe.append((a, b))
                report['maximum_safe_wordpieces'] = max(report['maximum_safe_wordpieces'], maximum)
                continue
            if b-a < 2:
                raise ValueError('Even one source character exceeds the Transformer limit; no text was discarded')
            middle = (a+b)//2
            # Subdivision always makes progress, including a single giant spaCy
            # token. Every source character remains covered; no retokenizer edit.
            half_overlap = min(overlap_chars//2, (b-a)//4)
            pending.extend([(middle-half_overlap, b, False), (a, middle+half_overlap, False)])
            report['subdivisions'] += 1
    result = sorted(set(safe))
    report['safe_windows'] = len(result)
    return result, report
