# TODO

- [ ] Character system completion
    - [x] CharacterCard + CharacterCompose wired into novel chapter generation
    - [ ] Character relationship tracking (affinity graph, interaction history)
    - [x] Actions + workflows + tests for batch character generation and validation
    - [x] Mental model engine: Big Five + Maslow + CBT + DIAMONDS + linguistic style + embodied perception + suffering
    - [ ] Personality archetypes + `closest_archetype()` lookup
    - [x] Tests: Maslow transitions, Big Five drift, age scaling, prompt gen, style extraction, somatic state,
      suffering accumulation, e2e `process_and_respond`
    - [ ] Evaluation framework (EMgine methodology, 3-layer validation, literary character test suite)
- [ ] Mental novel gen integration with character psychology.
    - [x] `NovelComposeMental` capability (seed → inject → evolve mental states per chapter)
    - [x] Actions: `GenerateNovelMental`, `GenerateChaptersFromScriptsWithMental` (+ RAG variants)
    - [x] Workflows: debug, validated, RAG, illustrated combo pipelines
    - [ ] Tests: mock-LLM round-trip for mental state chapter generation
