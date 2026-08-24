# TODO — fabricatio-capabilities

## New capability

- [x] Add `RatingImage` capability — rate images against criteria via a vision-capable LLM
    - [x] `RatingImage(Rating)` mixin: `rate_image(image, topic, criteria, ...)` accepting `str | Path`
    - [x] Vision plumbing via `LLMKwargs.images` (router auto-base64s bytes); `send_to` defaults to the `VISION` variant slot
    - [x] `built-in/rate_image` Handlebars template + config entry `rate_image_template`
    - [x] Reuses `build_rating_model` from `utils.py` for the bounded-score result model
    - [x] Mocked tests via `LLMTestRole` (`tests/test_rating_image.py`, 4 cases)

## Reduce CRAP scores flagged by `pytest --cov=fabricatio_capabilities --crap` (threshold 30)

- [ ] Cover `Rating.rate()` with mocked tests (CRAP 68.50, CC 10, cov 16.4% — coverage-limited, not structure-limited)
    - [ ] Single-text success via `LLMTestRole` → `dict[str, float]`
    - [ ] Batch with one failed item → `None` entry in list
    - [ ] Batch all-fail → all-`None` list
    - [ ] `manual=None` triggers `draft_rating_manual` fallback (mock drafting path)
- [ ] Split or test `formated_json_schema` (CRAP 65.89, CC 9, cov 11.1%) — branch-heavy schema formatting; extract pure helpers like `build_rating_model`
- [ ] Split or test `drafting_rating_weights_klee` (CRAP 40.39, CC 7, cov 12.0%) — Klee weight-drafting permutations; extract permutation/normalize core into `utils.py`
- [ ] Test `dispatch_task` (CRAP 30.00, CC 5, cov 0%) — lowest-effort win: branches are simple, just unexercised
