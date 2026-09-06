# TODO

- [ ] Add ComfyUI integration.
    - [x] Package skeleton + `ComfyUIClient` for prompt queue, progress polling, image retrieval
    - [x] Workflow template system with dynamic parameter injection
    - [x] `ComfyUIAction` + Python bindings + integration tests
    - [ ] WebSocket real-time progress tracking
    - [x] End-to-end integration test with running ComfyUI instance
- [ ] VLM quality gate with regeneration feedback loop.
    - [ ] After rendering, a VLM verdicts each image: technical glitches (artifacts, broken anatomy) AND coherence with the original intent (the proposed prompt / image description).
    - [ ] On failed verdict, feed the verdict back as feedback and re-propose the prompt / re-render (bounded retries, keep the best attempt).
    - [ ] Design still open (first `generate_verified` implementation was reverted as unsatisfactory): retry loop shape, budget semantics, and how the novel pipeline opts in. The judge-side building blocks are committed (``ImageVerdict``, ``VisuallyJudge``, ``built-in/image_verdict``), the comfyui-side loop is NOT implemented.
- [ ] Style-aligned, character-consistent story illustration.
    - [ ] Across a composed novel's renders, the visual style must stay aligned (one declared style anchor: fixed style prompt block + fixed always-on LoRA set + identical sampler knobs for every scene, not per-scene LLM drift).
    - [ ] Characters must stay the same person across scenes (identity reference: IPAdapter / PuLID / reference-image or LoRA per character; cast list gains a per-character visual identity binding).
    - [ ] Early idea — couples with the VLM gate above (verdict can also check identity/style drift against reference anchors).
