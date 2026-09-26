# TODO

- [ ] Novel scene image generation with ComfyUI.
    - [ ] Scene extraction from novel content + prompt engineering for image generation
    - [ ] `SceneImageAction` in `fabricatio-novel` calling `fabricatio-comfyui` to generate scene illustrations
    - [ ] Image embedding into novel output (EPUB/Typst) + configurable style/template selection
    - [ ] Per-chapter image caching + regeneration on content changes
- [ ] Stage vocabulary as a `StrEnum` — `StageName` is a `Literal` only because the digit-led names cannot be `auto()` values under `python-strenum-bare-auto`; either carry the layout prefix in the member values (`STAGE_01_INIT = auto()` → `stage_01_init`, so `--stage` and every example spell it) or rename the stages digit-free (`init … novel`), which invalidates the existing `stage_<name>` run directories. Then `ResumePoint.of` can take `StageName | None` and drop its `stage_` prefix tolerance.
- [x] `fabricatio-novel` support rag
- [x] Novel generation fix
- [x] Seal RAG out of the base context tree: standard novel generation shall not carry `rag: RagRetrieval | None` + `set_rag` on `NovelContext`/`ChapterContext`/`StoryContext`; move retrieval settings into a RAG-specific context subclass.
- [x] Resume a persisted staged run: `fanvl w|wr|wri --resume <run> [--stage <name>]` restarts at the named stage or the one after the run's newest snapshot, driving the same workflow in place — the stages already on disk leave themselves out, the state and the run's family come from the snapshot, and every refusal lands before the first LLM call.

