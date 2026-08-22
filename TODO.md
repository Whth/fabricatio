# TODO

- [ ] Add api support.
    - [ ] Define API types + REST route handlers + wire into axum server
    - [ ] Add CORS/error middleware + Python binding for server config
    - [ ] Integration tests + API docs
- [ ] Run as mcp server.
    - [ ] Feature flag + `McpServer` struct + tool registry + `tools/list`
    - [ ] stdio + HTTP transports + `tools/call` dispatch
    - [ ] Register Fabricatio tools as MCP tools + Python binding + tests
- [ ] Finalize the webui.
    - [ ] Chat interface + API client + WebSocket/SSE streaming
    - [ ] Config panel + agent status dashboard
    - [x] Error handling + loading states + UX polish
    - [ ] Wire Python execution bridge — hook `bridge.py` into Rust `/api/execute` via PyO3 so workflows actually run (
      currently just enqueues)
    - [ ] Workflow save/load — persist workflows as JSON (file or SQLite), load into editor
    - [ ] Clean up scaffolding — remove TheWelcome, HelloWorld, counter.ts, unused AboutView, default Vue assets
    - [ ] Undo/Redo — command pattern on workflow store (add/remove/move node, add/remove edge)
    - [ ] Dark/Light theme toggle — CSS variables + Pinia persistence
    - [ ] Real-time LLM token streaming — surface `WsMessage::LlmToken` in UI for streaming text output during
      generation
    - [ ] Workflow import/export — download as JSON, import from file, share workflows
    - [ ] Responsive layout — collapsible sidebars on mobile, resizable panels
- [ ] Add ComfyUI integration.
    - [x] Package skeleton + `ComfyUIClient` for prompt queue, progress polling, image retrieval
    - [x] Workflow template system with dynamic parameter injection
    - [x] `ComfyUIAction` + Python bindings + integration tests
    - [ ] WebSocket real-time progress tracking
    - [x] End-to-end integration test with running ComfyUI instance
- [ ] Novel scene image generation with ComfyUI.
    - [ ] Scene extraction from novel content + prompt engineering for image generation
    - [ ] `SceneImageAction` in `fabricatio-novel` calling `fabricatio-comfyui` to generate scene illustrations
    - [ ] Image embedding into novel output (EPUB/Typst) + configurable style/template selection
    - [ ] Per-chapter image caching + regeneration on content changes
- [ ] Add Plugin system.
    - [ ] Plugin protocol + registry + lifecycle (load/unload)
    - [ ] Hook points in core lifecycle + entry-point discovery
    - [ ] Plugin config support + validation + tests
- [x] Replace litellm with native rust impl
    - [x] Port deprecated mock utils to thryd impl
    - [x] Port tests to new mock utils
    - [x] Sync documentations
    - [x] Router cache support ttl and eviction
- [x] Add worktree-based isolated development subpackage
- [ ] Add level-based context compression subpackage
    - [ ] Package skeleton + `CompressionLevel` enum + compression strategies
    - [ ] Async compression + Python bindings + tests
- [ ] TreeSetter-based ACE
    - [ ] tree-sitter dep + AST node types + tree edit operations (insert/replace/delete/move)
    - [ ] TreeSetter orchestrator + Python bindings + multi-language round-trip tests
- [ ] Self-Extensible Agent
    - [ ] Capability protocol + runtime registry + dynamic method injection on Role
    - [ ] Config-based discovery + hot-reload + tests
- [x] Add more examples
- [x] Write missing examples (Structured Output, Extract, Improve)
- [x] Document undocumented examples + cross-link `use-cases.rst` + examples index
- [ ] `ToolExecuter` exec results feedback to llm
    - [x] Surface errors via `ApplicationError` + `ResultCollector.error()` + `last_error` template param
- [x] Use `stubgen` feat and `cfg_attr` to make the stub generation as an opt-in for all mixed packages.
- [x] Use `Thryd` impl to move some requests to rust side
    - [x] All core LLM operations already routed through `rust.router_usage`
- [x] Add Texts-based skill system, as a subpackage
    - [x] Skill YAML/JSON schema + loader + directory scanner
    - [x] Wire into Role + validation + example skill file + tests
- [x] Port build workflow to `Justfile`
- [x] `thryd::Router` use concurrent safe impl
- [x] Extract `Router` from `fabricatio-core` into standalone `fabricatio-router` crate
- [x] Replace parser with native rust impl
- [x] Better memory impl
- [x] RAG package refactor, move rerank and embedding to `thryd`
    - [x] Add Reranker support in `thryd`
    - [x] TEI as `Provider` in thryd (RerankerModel for OpenAI-compat: wontfix — OpenAI doesn't support rerankers)
    - [x] Wire `rerank()` into Router Python class + add `UseReranker` capability
- [x] Add embedding and rerank mock support to `fabricatio-mock`
    - [x] Add `add_or_update_dummy_embedding_model` and `add_or_update_dummy_reranker_model` to Router
    - [x] Add `setup_dummy_embeddings` / `setup_dummy_reranks` + response builders in `fabricatio-mock`
    - [x] Tests for embedding and rerank mock paths
- [x] Replace `UseLLM` with native rust impl
    - [x] Fix the mock utils that is break by the replacement.
    - [x] router support `no_cache`
- [x] Diff use `Hashline` impl instead of `StringGrep`
    - [x] Integrate `rho-hashline` crate + hash-based line anchoring in Rust
    - [x] Add `compute_hash`, `format_hashes`, `parse_hashline_anchor`, `apply_*` functions
- [x] Add `Diff.format_with_hashes()` method + Python exports + 22 tests
- [x] Add high-level `HashlineDiff` wrapper for hashline API
    - [x] `Diff` dataclass with anchor and line-number fields
    - [x] `from_anchors()` and `from_line_range()` factory methods
    - [x] `apply()` with line_range and pattern matching modes + tests
- [x] Convert `fabricatio-rag` to a pure python package
    - [x] Extract lancedb impl into a seperate package
- [x] `fabricatio-novel` support rag
- [x] Lancedb integration refactor
    - [x] Refactor `fabricatio-typst`
- [x] Milvus integration refactor
- [x] Novel generation fix
- [x] Embedding fail without any debug info fix
- [x] sparse cache for embedding
- [x] `Thryd` router support retry
- [x] Add VFS-based sandbox subpackage for isolated LLM file operations
    - [x] Rust crate: `VirtualFS` trait + in-memory tree (read/write/list/delete/stat) + overlay mount system (
      copy-on-write over real paths)
    - [x] Rust crate: diff snapshot & apply — `SandboxSession` tracking all mutations, producing a unified diff, and
      optionally writing changes back to real FS
    - [x] Python bindings (PyO3) for `VirtualFS`, `SandboxSession`, overlay mounts
    - [x] Tests — Rust unit tests for VFS ops + overlay + diff/apply; Python binding smoke tests
- [ ] Typst compilation
    - [ ] Integrate `typst-rs` or shell out to `typst compile` so `fabricatio-typst` Article model produces PDF output
    - [ ] Template library for common document types (paper, report, slides)
    - [ ] Python bindings + CLI (`fabricatio-typst compile`) + tests
- [ ] `fabricatio-rag` test suite
    - [ ] Unit tests for abstract RAG capability (add_document, afetch_document, refined_query, ranking)
    - [ ] Integration tests with `fabricatio-lancedb` and `fabricatio-milvus` backends
    - [ ] Edge-case tests: empty corpus, duplicate documents, concurrent add/fetch
- [ ] `fabricatio-anki` support image in cards.
    - [ ] Add `Image` field type to card models (not just `str` text fields)
    - [ ] LLM-driven image generation + bundling into `media/` for each card
    - [ ] Embed images into `.apkg` via compile_deck's existing media pipeline
    - [ ] Image field support in `GenerateDeck` capability (prompting, field schema, template injection)
    - [ ] Tests: image field round-trip, media bundling, .apkg integrity
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
- [ ] Judge integration with novel + RAG
    - [ ] Wire `EvidentlyJudge` / `VoteJudge` into novel pipeline for chapter quality gating
    - [ ] Add RAG relevance scoring action using judge capabilities
    - [ ] Actions + workflows + tests
- [ ] Web search action
    - [ ] `WebSearchAction` in `fabricatio-actions` backed by search API (Tavily/SerpAPI/DuckDuckGo)
    - [ ] `WebScrapeAction` for extracting content from fetched URLs
    - [ ] Wire into research workflow + tests
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
- [ ] Add multimodal LLM support (`aaskv` — text + image input).
    - [ ] `ContentPart` enum (`Text` / `ImageUrl`) + `content: Vec<ContentPart>` field on `CompletionRequest` — backward
      compatible (empty `content` falls back to `message` string)
    - [ ] OpenAI serialization: switch `.content(message)` to `.content(content_parts)` using `async-openai`'s existing
      `ChatCompletionRequestMessageContentPart` types
    - [ ] Cache key update: `prepare_input_text` concatenates text parts + image URLs for deterministic blake3 hashing
    - [ ] `fabricatio-router` PyO3: `completion_v(send_to, text, images: Option<Vec<Vec<u8>>>)` — raw bytes → base64
      data URIs, MIME sniffing, construct `ContentPart` list
    - [ ] Python `UseLLM.aaskv(text: str | list[str], images: bytes | list[bytes] | None)` — clean interface, no
      `ContentPart` exposure
    - [ ] Tests: text-only backward compat, single image, multi-image, batch mode
- [ ] Add `cargo clippy` + `cargo test` to CI
    - [ ] Fix ruff CI no-op (installs ruff but never runs `ruff check`)
    - [ ] Add clippy + cargo test steps to `.github/workflows/tests.yaml` matrix
- [x] Introduce Variant-based llm select, standardize llm calling procedure, which can reduce the config of the model
  needed
