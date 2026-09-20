# TODO

- [x] Add embedding and rerank mock support to `fabricatio-mock`
    - [x] Add `add_or_update_dummy_embedding_model` and `add_or_update_dummy_reranker_model` to Router
    - [x] Add `setup_dummy_embeddings` / `setup_dummy_reranks` + response builders in `fabricatio-mock`
    - [x] Tests for embedding and rerank mock paths

## Internalization backlog

Audit 2026-09-13: evidence is a scan of the 98 test files under `packages/*/python/tests` plus the
`thryd`/`fabricatio-router` sources. Counts are those of the scan, not estimates.

### Python-only — implemented (no consumer migrated yet)

- [x] `MockScript` (`models/mock_script.py`): named responses, strict install (padding 0 by default),
      `ScriptExhaustedError` naming every declared label, `reset_on_exit` / `clear()`.
      Replaces positional FIFO stacks (167 `install_router_usage` call sites; stacks up to 14 entries).
      Not delivered: counting *unused* responses — the router binding exposes no queue getter, so only
      over-consumption is detectable.
- [x] `make_test_role(*capabilities, name=...)` (composed, memoized class) and the opt-in plugin module
      (`pytest_plugin.py`: fixtures `mock_role`, `mock_script`, `stub_template`; loaded with
      `-p fabricatio_mock.pytest_plugin` or a `pytest_plugins` line, no `pytest11` entry point).
      Removes the 49 empty test-role classes and their paired fixtures.
      Not delivered: an autouse reset fixture — it would change behaviour for every suite in an
      environment where the package is installed, which the "no consumer migration yet" constraint rules out.
- [x] Payload builders: `Value.from_text/from_model/from_json/from_python/from_generic/from_raw` and
      `return_obj_router_usage` (unfenced JSON). A judge-specific `return_bool_router_usage` was dropped:
      the judge path proposes `JudgeMent` JSON models, which `return_model_json_router_usage` already covers.
- [x] Deterministic doubles: `hash_embedding` (shake_256 → unit vector, stable across runs),
      `rank_by_overlap`, `setup_fake_embeddings` / `install_fake_embeddings`,
      `setup_fake_reranks` / `install_fake_reranks` (batch-aware; the older helpers only wrap one vector
      per response, so they cannot describe a multi-text call).
- [x] `stub_template(name, body)` and `clear_dummy_responses(group)`.
      Config overrides stay with the native tools (`dataclasses.replace(cfg, field=value)`,
      `cfg.model_copy(deep=True)` plus direct assignment) instead of a `**fields` helper that
      erases the per-field types.
- [x] Flat re-exports in `fabricatio_mock/__init__.py`; `models/mock_role.py` now imports the group
      constants from `constants.py`, the single source for group names and dummy model ids.
      Not delivered: deleting the docstring-only `capabilities/`, `actions/`, `workflows/` packages and
      the no-op `MockConfig` — cleanup rather than a feature, and nothing imports them.

### Needs Rust bindings (`fabricatio-router` / `thryd`)

- [ ] Request capture: `enable_request_log(group)` / `dummy_requests(group)` + prompt assertions.
      Removes the 15 `patch.object` sites on `aask`/`propose`/`alist_v`/`hashline_diff` that exist only
      because the router mock cannot observe what was sent. Also the prerequisite for reporting unused
      script responses.
- [ ] Error injection: expose `DummyModel::with_completion_errors` (exists at
      `crates/thryd/src/models/dummy.rs:123`) as `install_dummy_errors(group, ...)`.
- [x] Cache isolation for dummy traffic: `no_cache` only bypasses the read, so mock answers used to be
      written into the shared production cache (`.cache.db.heed`), whose completion key is `blake3(message)`
      alone; a warm entry also served mock tests without consuming the queue. Root cause of the manual
      `uuid4` prompt salting. Landed as the separate `no_store` flag (write-side twin of `no_cache`) on the
      four router entry points, plumbed through `[llm]`/`[embedding]`/`[reranker]` config and the scoped
      `*_no_store` fields. `LLMTestRole` now sets both flags for LLM, embedding and reranker traffic, so the
      suites carry no prompt salt or run token; `EmbeddingScopedConfig.embedding_no_cache` also defaulted to
      `False`, blocking the CONFIG fallback and `hold_to` propagation, and is now `None` like its siblings.
- [ ] Variant pinning: `CONFIG.pin_llm_variants(DUMMY_LLM_GROUP)` with save/restore. Removes the
      hand-copied `_resolve_completion_send_to` overrides and import-time global config mutation.
- [ ] Predicate-matched responses `(matcher, response)` in `DummyModel` so response order stops
      mattering; makes `MockScript` simpler.

### Adoption notes

- Consumers keep their current imports; the new surface is additive.
- The plugin is opt-in: `pytest -p fabricatio_mock.pytest_plugin`, or a `pytest_plugins` line in a
  suite's `conftest.py`. The package registers no entry point, so installing it changes nothing for
  existing suites.
- Pre-existing failures in `packages/fabricatio-novel/python/tests` (planning ×2, overlap, RAG
  illustration workflow) reproduce identically with HEAD's pristine `fabricatio_mock` shadowed through
  `PYTHONPATH`, so they are unrelated to this work.
