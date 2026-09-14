def mark_entity(text, entity_start, entity_end):
    """Wrap one entity occurrence in the canonical training-data markers."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if type(entity_start) is not int or type(entity_end) is not int:
        raise TypeError("entity_start and entity_end must be integers")
    if not 0 <= entity_start < entity_end <= len(text):
        raise ValueError(
            "entity offsets must satisfy "
            "0 <= entity_start < entity_end <= len(text)"
        )

    return (
        f"{text[:entity_start]}[ENTITY] "
        f"{text[entity_start:entity_end]} [/ENTITY]{text[entity_end:]}"
    )
