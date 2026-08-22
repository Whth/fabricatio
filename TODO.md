# TODO

Repo-level items only — package-scoped TODOs live next to their code in each
package's own `TODO.md` (e.g. `packages/fabricatio-webui/TODO.md`,
`crates/thryd/TODO.md`).

- [ ] Add level-based context compression subpackage
    - [ ] Package skeleton + `CompressionLevel` enum + compression strategies
    - [ ] Async compression + Python bindings + tests
- [ ] TreeSetter-based ACE
    - [ ] tree-sitter dep + AST node types + tree edit operations (insert/replace/delete/move)
    - [ ] TreeSetter orchestrator + Python bindings + multi-language round-trip tests
- [x] Add more examples
- [x] Write missing examples (Structured Output, Extract, Improve)
- [x] Document undocumented examples + cross-link `use-cases.rst` + examples index
- [x] Port build workflow to `Justfile`
- [ ] Add TTS subpackage (abstract interface + provider implementations).
    - [ ] `fabricatio-tts` pure python package: `UseTTS` capability mixin + `TTSConfig` + `AudioChunk` streaming model +
      `SynthesisResult` output type
    - [ ] `TTSProvider` protocol (async `synthesize(text, voice, params) → AsyncIterator[AudioChunk]`) + voice
      discovery + SSML support
    - [ ] Provider implementations as separate packages (e.g. `fabricatio-tts-openai`, `fabricatio-tts-elevenlabs`,
      `fabricatio-tts-piper`) each wiring `TTSProvider` to its backend API
    - [ ] Event-system bridge: emit `tts:chunk`, `tts:start`, `tts:end` events for real-time streaming playback +
      interruption via `Event`
    - [ ] Integration with `fabricatio-core` templates (Handlebars `{{speak}}` helper) + Python bindings + tests
- [ ] Add session replay + workflow continue.
    - [ ] Record step timeline in `WorkFlow.serve()`:
      `(step_index, action_name, output_key, duration_ms, success, error)` per action — ~30 lines instrumentation
    - [ ] Auto-checkpoint before each action via `CheckPointStore.save()` — leverage existing shadow git for workspace
      rollback on resume
    - [ ] `fabricatio-session` crate: SQLite-backed run log + replay engine — `<1KB` per workflow run, no context dict
      serialization needed (thryd cache + checkpoint handle reconstruction)
    - [ ] `WorkFlow.resume(run_id)`: read run log → `checkpoint.reset(last_commit)` → re-run steps 1..N-1 (LLM cache
      hits, instant) → fresh execution at failed step N
    - [ ] Actions declare `idempotent: bool` — non-idempotent steps flagged for manual review instead of auto re-run
    - [ ] WebUI timeline viewer: scrub through action execution history, per-step expand for LLM input/output
- [ ] Add `cargo clippy` + `cargo test` to CI
    - [ ] Fix ruff CI no-op (installs ruff but never runs `ruff check`)
    - [ ] Add clippy + cargo test steps to `.github/workflows/tests.yaml` matrix
