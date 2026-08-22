# TODO

- [ ] `fabricatio-anki` support image in cards.
    - [ ] Add `Image` field type to card models (not just `str` text fields)
    - [ ] LLM-driven image generation + bundling into `media/` for each card
    - [ ] Embed images into `.apkg` via compile_deck's existing media pipeline
    - [ ] Image field support in `GenerateDeck` capability (prompting, field schema, template injection)
    - [ ] Tests: image field round-trip, media bundling, .apkg integrity
