<p align="center">   
<picture>
        <img src="./assets/band.png" width="80%" alt="Fabricatio Logo" loading="lazy">
</picture>
</p>



<p align="center">
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
  </a>
  <a href="https://pypi.org/project/fabricatio/">
    <img src="https://img.shields.io/pypi/pyversions/fabricatio" alt="Python Versions">
  </a>
  <a href="https://pypi.org/project/fabricatio/">
    <img src="https://img.shields.io/pypi/v/fabricatio" alt="PyPI Version">
  </a>
  <a href="https://deepwiki.com/Whth/fabricatio">
    <img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki">
  </a>
  <a href="https://pepy.tech/projects/fabricatio">
    <img src="https://static.pepy.tech/badge/fabricatio/week" alt="PyPI Downloads (Week)">
  </a>
  <a href="https://pepy.tech/projects/fabricatio">
    <img src="https://static.pepy.tech/badge/fabricatio" alt="PyPI Downloads">
  </a>
  <a href="https://github.com/PyO3/pyo3">
    <img src="https://img.shields.io/badge/bindings-pyo3-green" alt="Bindings: PyO3">
  </a>

  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange" alt="Build Tool: uv + maturin">
  </a>

</p>


<p align="center">


  <a href="https://github.com/Whth/fabricatio/actions/workflows/build-package.yaml">
    <img src="https://github.com/Whth/fabricatio/actions/workflows/build-package.yaml/badge.svg" alt="Build Package">
  </a>
  <a href="https://github.com/Whth/fabricatio/actions/workflows/ruff.yaml">
    <img src="https://github.com/Whth/fabricatio/actions/workflows/ruff.yaml/badge.svg" alt="Ruff Lint">
  </a>
  <a href="https://github.com/Whth/fabricatio/actions/workflows/tests.yaml">
    <img src="https://github.com/Whth/fabricatio/actions/workflows/tests.yaml/badge.svg" alt="Tests">
  </a>
  <a href="https://coveralls.io/github/Whth/fabricatio?branch=master">
    <img src="https://coveralls.io/repos/github/Whth/fabricatio/badge.svg?branch=master" alt="Coverage Status">
  </a>
  <a href="https://fabricatio.readthedocs.io/en/latest/?badge=fabricatio">
    <img src="https://readthedocs.org/projects/fabricatio/badge/?version=latest" alt="Documentation Status">
  </a>
  <a href="https://github.com/Whth/fabricatio/issues">
    <img src="https://img.shields.io/github/issues/Whth/fabricatio" alt="GitHub Issues">
  </a>
  <a href="https://github.com/Whth/fabricatio/pulls">
    <img src="https://img.shields.io/github/issues-pr/Whth/fabricatio" alt="GitHub Pull Requests">
  </a>
  <a href="https://github.com/Whth/fabricatio/stargazers">
    <img src="https://img.shields.io/github/stars/Whth/fabricatio" alt="GitHub Stars">
  </a>
</p>



---

## Overview

Fabricatio is a streamlined Python library for building LLM applications using an event-based agent structure. It
leverages Rust for performance-critical tasks, Handlebars for templating, and PyO3 for Python bindings.

## Features

- **Event-Driven Architecture**: Robust task management through an EventEmitter pattern.
- **LLM Integration & Templating**: Seamlessly interact with large language models and dynamic content generation.
- **Async & Extensible**: Fully asynchronous execution with easy extension via custom actions and workflows.

## TODO

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
- [ ] Placeholder based multiple-agents edits
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
    - [ ] Integration with `fabricatio-core` file I/O hooks so Actions transparently operate inside a sandbox
    - [x] Tests — Rust unit tests for VFS ops + overlay + diff/apply; Python binding smoke tests
- [ ] Typst compilation
    - [ ] Integrate `typst-rs` or shell out to `typst compile` so `fabricatio-typst` Article model produces PDF output
    - [ ] Template library for common document types (paper, report, slides)
    - [ ] Python bindings + CLI (`fabricatio-typst compile`) + tests
- [ ] `fabricatio-rag` test suite
    - [ ] Unit tests for abstract RAG capability (add_document, afetch_document, refined_query, ranking)
    - [ ] Integration tests with `fabricatio-lancedb` and `fabricatio-milvus` backends
    - [ ] Edge-case tests: empty corpus, duplicate documents, concurrent add/fetch
- [ ] Character system completion
    - [ ] Wire `CharacterCard` + `CharacterCompose` into `fabricatio-novel` chapter generation for consistency
    - [ ] Character relationship tracking (affinity graph, interaction history)
    - [ ] Actions + workflows + tests for batch character generation and validation
    - [ ] Mental model: Big Five + Maslow combined psychological state engine
        - [ ] Data models: `BigFiveProfile` (5D float 0-100) + `MaslowLevel` enum + `MentalState` (merged personality +
          need + emotion + cognitive bias)
        - [ ] `BigFiveProfile.distance_to()` for personality similarity; `as_vector()` for serialization
        - [ ] `EventImpact` structured model: `threatens_need`, `fulfills_need`, `personality_shift`, `emotion`,
          `emotion_intensity`, `triggers_bias`
        - [ ] `MindEngine.analyze_event()`: LLM-driven event → `EventImpact` extraction with `MentalState` as context
        - [ ] `MindEngine.apply_impact()`: deterministic rules for Maslow level drop (threat-based instant) and rise (
          satisfaction-accumulation threshold ≥3)
        - [ ] Age-based personality shift scale: child (3.0×), adolescent (1.5×), young adult (0.5×), adult (0.2×)
        - [ ] `MindEngine.build_system_prompt()`: translate `MentalState` into LLM hard constraints (personality rules,
          need focus, emotion style, cognitive bias examples)
        - [ ] `MentalState` persistence: snapshot per event for rollback and trajectory visualization
        - [ ] Personality archetypes: pre-defined `BigFiveProfile` points (hero, villain, sage, fool, outcast) +
          `closest_archetype()` lookup
        - [ ] DIAMONDS event taxonomy (Rauthmann et al., 2014): 8-dimensional situational classification replacing
          boolean event flags
            - [ ] `SituationProfile` model with 8 float dimensions (Duty, Intellect, Adversity, Mating, pOsitivity,
              Negativity, Deception, Sociality)
            - [ ] LLM-driven event → `SituationProfile` extraction (structured output with per-dimension 0-1 scores)
            - [ ] Dimension → distortion mapping: Adversity→catastrophizing, Deception→personalization,
              Negativity→emotional_reasoning, etc.
            - [ ] Wire into `CognitiveEngine._rule_filter()`: use dimension scores instead of boolean flags for
              distortion boost calculation
        - [ ] CBT cognitive distortion engine (hybrid: rule filter + LLM refinement)
            - [ ] `CognitiveDistortion` enum (catastrophizing, black-and-white, personalization, emotional reasoning,
              should-thinking)
            - [ ] `CognitiveProfile`: per-character distortion tendency weights (0-100 each) + `most_likely()` sort
            - [ ] `DistortionAnalysis` structured model: `triggered_distortion`, `internal_monologue`, `reasoning`
            - [ ] `CognitiveEngine._rule_filter()`: DIAMONDS dimension scores → distortion score boost
            - [ ] `CognitiveEngine._generate_monologue()`: cheap LLM call for internal monologue only (high-confidence
              path)
            - [ ] `CognitiveEngine._llm_analyze()`: full LLM structured extraction from top-3 candidates (low-confidence
              path)
            - [ ] Confidence threshold: if top candidate score > 70 → use rule result + monologue generation; else →
              full LLM analysis
            - [ ] Wire into `MindEngine`: CBT as event pre-filter before Maslow impact assessment (distortion shapes
              interpretation, interpretation shapes need impact)
        - [ ] Linguistic style decoupling (TTM, Zhan et al., 2025): separate "what to say" from "how to say"
            - [ ] `LinguisticStyle` model: `preferences` (natural language description), `common_pronouns`,
              `common_modals`, `common_adjectives`, `style_references`
            - [ ] `extract_style()`: LLM-driven extraction from character's historical dialogues
            - [ ] Three-stage generation: styleless response (personality+memory) → memory-checked response (RAG
              correction) → stylized response (style transfer)
            - [ ] Style references: retrieve semantically similar utterances from character history as rewriting
              templates
            - [ ] Wire into `MindEngine.build_system_prompt()`: inject linguistic style constraints alongside
              personality and emotion
        - [ ] Embodied perception (EFT-CoT, Du et al., 2026): somatic awareness as first stage of emotional processing
            - [ ] Three-stage emotional pipeline: Embodied Perception → Cognitive Exploration → Narrative Intervention
            - [ ] `SomaticState` model: body sensations mapped from emotion type + intensity (e.g. fear→racing heart,
              tight chest, trembling)
            - [ ] `CognitiveExploration`: extract core beliefs and underlying thoughts from somatic experience
            - [ ] `NarrativeIntervention`: restructure character's self-narrative based on cognitive insights
            - [ ] Wire into `MindEngine`: emotion triggers somatic state → somatic state informs prompt constraints for
              physical descriptions
        - [ ] Qualitative Suffering States (Emotional Cost Functions, Mopgar, 2026): irreversible trauma that reshapes
          character
            - [ ] `QualitativeSuffering` model: `what_was_lost`, `the_void`, `how_it_changed_me`, `anticipatory_dread`
            - [ ] Four-component architecture: Consequence Processor → Character State → Anticipatory Scan → Story
              Update
            - [ ] Experiential dread: from character's own lived consequences
            - [ ] Pre-experiential dread: acquired without direct experience (from others' stories or cultural
              knowledge)
            - [ ] Suffering accumulates and reshapes character — not a temporary state but a permanent modification to
              MentalState
            - [ ] Wire into `MindEngine`: traumatic events create QualitativeSuffering entries that persist and
              influence future interpretations
        - [ ] Three-layer separation: analysis (LLM with schema) → update (deterministic rules) → alignment (prompt
          injection)
        - [ ] Tests: Maslow level transitions, Big Five drift under events, age scaling, prompt generation, linguistic
          style extraction, somatic state mapping, suffering accumulation, end-to-end `process_and_respond`
        - [ ] Evaluation framework (EMgine methodology + three-layer validation)
            - [ ] Layer 1: Theory consistency — automated assertions checking psychological predictions (target > 90%
              pass rate)
            - [ ] Layer 2: Reader perception — LLM-as-Judge + human evaluation for believability (target > 7.5/10)
            - [ ] Layer 3: Trajectory consistency — automated checks for sudden jumps, reversals, dead spots across
              event sequences
            - [ ] Literary character test suite: Hamlet, Lin Daiyu, Julien Sorel — known characters as regression test
              baseline
            - [ ] `evaluate_model()` orchestrator running all three layers against test suite
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

## Installation

```bash
# install fabricatio with full capabilities.
pip install fabricatio[full]

# or with uv

uv add fabricatio[full]


# install fabricatio with only rag and rule capabilities.
pip install fabricatio[rag,rule]

# or with uv

uv add fabricatio[rag,rule]

```

You can download the templates from the github release manually and extract them to the work directory.

```bash
curl -L https://github.com/Whth/fabricatio/releases/download/v0.19.1/templates.tar.gz | tar -xz
```

Or you can use the cli `tdown` bundled with `fabricatio` to achieve the same result.

```bash
tdown download --verbose -o ./
```

> Note: `fabricatio` performs template discovery across multiple sources with filename-based identification. Template
> resolution follows a priority hierarchy where working directory templates override templates located in
`<ROAMING>/fabricatio/templates`.

## Usage

### Basic Example

```python
"""Example of a simple hello world program using fabricatio."""

from typing import Any

# Import necessary classes from the namespace package.
from fabricatio import Action, Event, Role, Task, WorkFlow, logger


# Create an action.
class Hello(Action):
    """Action that says hello."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


# Create the role and register the workflow.
(Role()
 .subscribe(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
 .dispatch())

# Make a task and delegate it to the workflow registered above.
assert Task(name="say hello").delegate_blocking("talk") == "Hello fabricatio!"

```

### Examples

For various usage scenarios, refer to the following examples:

- Simple Chat
- Structured Output
- Extraction
- Content Improvement
- Retrieval-Augmented Generation (RAG)
- Article Extraction
- Propose Task
- Code Review
- Write Outline

_(For full example details, see [Examples](./examples))_

## Configuration

Fabricatio supports flexible configuration through multiple sources, with the following priority order:
`Call Arguments` > `./.env` > `Environment Variables` > `./fabricatio.toml` > `./pyproject.toml` >
`<ROMANING>/fabricatio/fabricatio.toml` > `Builtin Defaults`.

Below is a unified view of the same configuration expressed in different formats:

### Environment variables or dotenv file

```dotenv
FABRICATIO_LLM__SEND_TO=openai/gpt-3.5-turbo
FABRICATIO_LLM__TEMPERATURE=1.0
FABRICATIO_LLM__TOP_P=0.35
FABRICATIO_LLM__STREAM=false
FABRICATIO_LLM__MAX_COMPLETION_TOKENS=8192
FABRICATIO_DEBUG__LOG_LEVEL=INFO
```

### `fabricatio.toml` file

```toml
[debug]
log_level = "DEBUG"


[llm]
send_to = "base" # send req to `base` group by default
max_completion_tokens = 32000
stream = false
temperature = 1.0
top_p = 0.35


[routing]
providers = [
    { ptype = "OpenAICompatible", key = "sk-...", name = "mm", base_url = "https://api.example.com/v1/" }
]

completion_deployments = [
    { id = "mm/a-completion-model", group = 'base', tpm = 100_000, rpm = 1000 }
]
cache_database_path = "path/to/.cache.db"

```

### `pyproject.toml` file

```toml
[tool.fabricatio.debug]
log_level = "DEBUG"


[tool.fabricatio.llm]
send_to = "base" # send req to `base` group by default
max_completion_tokens = 32000
stream = false
temperature = 1.0
top_p = 0.35


[tool.fabricatio.routing]
providers = [
    { ptype = "OpenAICompatible", key = "sk-...", name = "mm", base_url = "https://api.example.com/v1/" }
]

completion_deployments = [
    { id = "mm/a-completion-model", group = 'base', tpm = 100_000, rpm = 1000 }
]
cache_database_path = "path/to/.cache.db"


```

## Contributing

We welcome contributions from everyone! Before contributing, please read our [Contributing Guide](CONTRIBUTING.md)
and [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Fabricatio is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

Special thanks to the contributors and maintainers of:

- [PyO3](https://github.com/PyO3/pyo3)
- [Maturin](https://github.com/PyO3/maturin)
- [Handlebars.rs](https://github.com/sunng87/handlebars-rust)
