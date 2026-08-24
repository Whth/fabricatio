# TODO — fabricatio-capabilities

## New capability

- [ ] Add `RatingImage` capability — rate images against criteria via a vision-capable LLM
    - [ ] `RatingImage(Rating)` mixin mirroring `rate()` but accepting image input (`str | Path` local path or URL) alongside the rating manual
    - [ ] Vision-LLM plumbing: encode/attach image(s) in the completion request (extend `UseLLM` call path or reuse existing multimodal support in the router)
    - [ ] `built-in/rate_image` Handlebars template + config entry `rate_image_template` under `[ext.capabilities]`
    - [ ] Reuse `build_rating_model` from `utils.py` for the bounded-score result model
    - [ ] Mocked tests via `LLMTestRole` (single/batch/fallback branches, same shape as the `rate()` coverage TODO above)

## Reduce CRAP scores flagged by `pytest --cov=fabricatio_capabilities --crap` (threshold 30)

- [ ] Cover `Rating.rate()` with mocked tests (CRAP 68.50, CC 10, cov 16.4% — coverage-limited, not structure-limited)
    - [ ] Single-text success via `LLMTestRole` → `dict[str, float]`
    - [ ] Batch with one failed item → `None` entry in list
    - [ ] Batch all-fail → all-`None` list
    - [ ] `manual=None` triggers `draft_rating_manual` fallback (mock drafting path)
- [ ] Split or test `formated_json_schema` (CRAP 65.89, CC 9, cov 11.1%) — branch-heavy schema formatting; extract pure helpers like `build_rating_model`
- [ ] Split or test `drafting_rating_weights_klee` (CRAP 40.39, CC 7, cov 12.0%) — Klee weight-drafting permutations; extract permutation/normalize core into `utils.py`
- [ ] Test `dispatch_task` (CRAP 30.00, CC 5, cov 0%) — lowest-effort win: branches are simple, just unexercised
