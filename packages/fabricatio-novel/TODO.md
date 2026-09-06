# TODO

- [ ] Novel scene image generation with ComfyUI.
    - [ ] Scene extraction from novel content + prompt engineering for image generation
    - [ ] `SceneImageAction` in `fabricatio-novel` calling `fabricatio-comfyui` to generate scene illustrations
    - [ ] Image embedding into novel output (EPUB/Typst) + configurable style/template selection
    - [ ] Per-chapter image caching + regeneration on content changes
- [x] `fabricatio-novel` support rag
- [x] Novel generation fix
- [ ] Seal RAG out of the base context tree: standard novel generation shall not carry `rag: RagRetrieval | None` + `set_rag` on `NovelContext`/`ChapterContext`/`StoryContext`; move retrieval settings into a RAG-specific context subclass.

