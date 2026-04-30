Rust Crates
===========

Fabricatio's performance-critical components are implemented in Rust as independent crates,
providing high-performance routing, caching, and system integration for the Python ecosystem.

thryd
-----

**Router Engine** - High-performance LLM request routing with intelligent caching and rate limiting.

.. code-block:: text

    thryd/
    ├── src/
    │   ├── lib.rs              # Main entry point, exports
    │   ├── router.rs           # Core routing engine
    │   ├── cache.rs            # redb-based persistent cache
    │   ├── rate_limiter.rs     # TPM/RPM sliding window limiter
    │   ├── provider.rs         # Provider trait & OpenAI-compatible impl
    │   ├── model.rs            # Completion & embedding models
    │   ├── deployment.rs       # Deployment with usage tracking
    │   ├── tracker.rs          # Token usage tracking (tiktoken)
    │   ├── error.rs            # ThrydError enum
    │   └── constants.rs        # Rate limiting constants
    └── README.md

Key Features:

- **Multi-Provider Routing**: OpenAI-compatible APIs, custom providers via trait
- **Intelligent Caching**: redb embedded database with automatic request deduplication
- **Token Tracking**: Accurate counting via tiktoken with TPM/RPM quotas
- **Rate Limiting**: Sliding window algorithm (60 buckets × 60s default)
- **Load Balancing**: Route to multiple deployments in a group
- **Async-First**: Built on Tokio for high-concurrency workloads
- **PyO3 Bindings**: Optional Python access via ``thryd`` Python package

.. code-block:: python

    # Python usage (via PyO3)
    from fabricatio_core.llm import LLM

    llm = LLM()
    response = await llm.aask("Hello", send_to="base")

thryd Architecture
~~~~~~~~~~~~~~~~~~

.. code-block:: text

     ┌─────────────────────────────────────────────────────────────────────┐
     │                         thryd Router                                  │
     │                                                                      │
     │  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────┐   │
     │  │   Provider   │  │    Cache      │  │     Rate Limiter       │   │
     │  │   Manager    │  │   (redb)     │  │  (TPM/RPM Sliding)     │   │
     │  └──────┬───────┘  └───────┬───────┘  └───────────┬─────────────┘   │
     │         │                   │                      │                 │
     │         └───────────────────┼──────────────────────┘                 │
     │                             │                                        │
     │                        ┌────┴────┐                                    │
     │                        │ Router  │                                    │
     │                        │ Engine  │                                    │
     │                        └────┬────┘                                    │
     │                             │                                         │
     │         ┌───────────────────┼───────────────────┐                     │
     │         ▼                   ▼                   ▼                     │
     │  ┌────────────┐      ┌────────────┐     ┌────────────┐               │
     │  │ Deployment │      │ Deployment │     │ Deployment │               │
     │  │ (gpt-4)    │      │ (gpt-3.5)  │     │ (claude-3) │               │
     │  │ RPM: 60    │      │ RPM: 1000  │     │ RPM: 20    │               │
     │  │ TPM: 100k  │      │ TPM: 200k  │     │ TPM: 80k   │               │
     │  └────────────┘      └────────────┘     └────────────┘               │
     └─────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────┐
                        │   LLM Provider APIs      │
                        │  OpenAI │ Anthropic │ ... │
                        └──────────────────────────┘

Core Concepts
^^^^^^^^^^^^^

**Providers** (``Provider`` trait)
    API service wrappers. Built-in: ``OpenAICompatible``, ``DummyProvider``.
    Implement the trait to add custom providers.

**Models** (``CompletionModel``, ``EmbeddingModel``)
    Specific LLM instances with API interaction logic.

**Deployments** (``Deployment``)
    Models wrapped with rate limiting and usage tracking.

**Routers** (``Router<CompletionTag>``, ``Router<EmbeddingTag>``)
    Manage multiple deployments, route requests by group name.

.. code-block:: rust

    // Rust usage example
    use thryd::*;
    use secrecy::SecretString;
    use std::sync::Arc;

    let api_key = SecretString::from("sk-...".to_string());
    let provider = Arc::new(OpenaiCompatible::openai(api_key));

    let mut router = Router::<CompletionTag>::default();
    router.add_provider(provider)?;
    router.deploy(
        "base".to_string(),
        "openai::gpt-4".to_string(),
        Some(60),        // RPM
        Some(100_000),   // TPM
    )?;

    let response = router.invoke("base".to_string(), request).await?;

Rate Limiting Internals
^^^^^^^^^^^^^^^^^^^^^^^

Thryd uses a **sliding window algorithm** with configurable parameters:

- **BUCKET_COUNT**: Number of time buckets (default: 60)
- **BUCKETS_WINDOW_S**: Window size in seconds (default: 60)

.. code-block:: text

    Sliding Window Rate Limiter:

    Time ──────────────────────────────────────────────────────►

    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │...│59 │  ← 60 buckets
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
      ▲                                   │
      │                                   │
    older                              newer
    (exits window)                      (enters)

    Each request increments bucket based on timestamp.
    RPM/TPM = sum of all buckets within window.

fabricatio-config
-----------------

**Configuration Management** - Multi-source configuration loading with validation.

.. code-block:: text

    fabricatio-config/
    ├── src/
    │   ├── lib.rs              # Config struct, Python bindings
    │   ├── loader.rs           # Figment-based config loading
    │   ├── env.rs              # Environment variable parsing
    │   ├── validation.rs        # Validator trait impls
    │   └── secret.rs           # SecretStr for API keys
    └── README.md

Features:

- **Multi-Source Loading**: env, TOML, pyproject.toml, global config
- **Validation**: URL, range, and type validation via validator crate
- **Secret Handling**: SecretStr for API keys with redaction in logs
- **PyO3 Integration**: Full Python class generation

Configuration Sources (priority order):

1. Call arguments (Python API)
2. ``.env`` file
3. Environment variables
4. ``./fabricatio.toml``
5. ``./pyproject.toml`` ``[tool.fabricatio]``
6. ``<ROAMING>/fabricatio/fabricatio.toml``
7. Built-in defaults

Configuration Structure:

.. code-block:: text

    [debug]
    log_level = "DEBUG"

    [llm]
    send_to = "base"
    max_completion_tokens = 32000
    stream = false
    temperature = 1.0
    top_p = 0.35

    [routing]
    providers = [...]
    completion_deployments = [...]

fabricatio-logger
-----------------

**Structured Logging** - Performance-optimized logging with loguru-style formatting.

.. code-block:: text

    fabricatio-logger/
    ├── src/
    │   ├── lib.rs              # Main entry, init functions
    │   ├── formatter.rs        # Custom FormatEvent impl
    │   └── writer.rs           # Output handling, rotation
    └── README.md

Features:

- **Loguru-Style Format**: ANSI colors, module/line context
- **Log Rotation**: never, minutely, hourly, daily options
- **Thread-Safe**: Global logger with Tokio runtime support
- **Python Integration**: Auto-configure from Python settings

Log Levels: TRACE < DEBUG < INFO < WARN < ERROR

fabricatio-constants
--------------------

**Shared Constants** - Application-wide path and variable definitions.

.. code-block:: text

    fabricatio-constants/
    ├── src/
    │   ├── lib.rs              # Exports all constants
    │   ├── paths.rs            # Platform-aware path constants
    │   ├── limits.rs           # Rate/limit constants
    │   └── defaults.rs         # Default values
    └── README.md

Platform Paths:

===========  ===============================================
Platform     Config Directory
===========  ===============================================
Linux        ``$XDG_CONFIG_HOME`` or ``$HOME/.config``
macOS        ``$HOME/Library/Application Support``
Windows      ``{FOLDERID_RoamingAppData}``
===========  ===============================================

fabricatio-stubgen
------------------

**Stub Generator** - Python ``.pyi`` stub file generation for PyO3 modules.

.. code-block:: text

    fabricatio-stubgen/
    ├── src/
    │   ├── lib.rs              # Main entry
    │   ├── generator.rs        # Stub generation logic
    │   └── templates.rs        # Stub templates
    └── README.md

Features:

- **Automatic Discovery**: Scans packages for PyO3 bindings
- **Type Annotations**: Full signatures in generated ``.pyi`` files
- **Multi-Package**: Handles all fabricatio packages in one run
- **Opt-In**: Enabled via ``stubgen`` feature flag

Additional Crates
-----------------

**tex-convertor** - LaTeX to Typst conversion

.. code-block:: text

    tex-convertor/
    └── src/lib.rs              # regex + tex2typst-rs

**scanner** - Python package filesystem scanner

.. code-block:: text

    scanner/
    └── src/lib.rs              # pep508_rs, walkdir, rayon

**error-mapping** - Error type mapping between Rust/Python

.. code-block:: text

    error-mapping/
    └── src/lib.rs              # cfg-if feature gating, various deps

**mcp-manager** - Model Context Protocol server management

.. code-block:: text

    mcp-manager/
    └── src/lib.rs              # rmcp client, tokio async

**deck_loader** - Anki deck file loading/generation

.. code-block:: text

    deck_loader/
    └── src/lib.rs              # genanki-rs-rev, csv, yaml

**signify** (v0.1.1) - JSON Schema to Python signature converter

.. code-block:: text

    signify/
    └── src/lib.rs              # heck, serde, serde_json

Features:

- ``schema_to_signature(&Value) -> String`` - Python function signature from JSON Schema
- ``schema_to_docstring_args(&Value) -> String`` - Google-style Args section
- Snake_case conversion of property names
- Type mapping: string, number, integer, boolean, array, object
- Required/optional parameter ordering with ``Optional[T]`` wrapping

**macro-utils** (v0.1.1) - Procedural macro utilities

.. code-block:: text

    macro-utils/
    └── src/lib.rs              # quote, syn (proc-macro crate)

Features:

- Single derive macro: ``TemplateDefault``
- Generates ``Default`` impls for structs with ``_template`` suffixed fields
- Supports optional ``#[suffix(...)]`` attribute for custom suffixes

**utils** (v0.1.2) - Shared utility functions

.. code-block:: text

    utils/
    └── src/lib.rs              # No external dependencies

Features:

- Single public function: ``mwrap<T>(item: T) -> Arc<Mutex<T>>``
- Thread-safe shared mutable ownership wrapper
- Combines Arc (atomic reference counting) with Mutex (mutual exclusion)

Rust Crate Dependencies
-----------------------

.. code-block:: text

    fabricatio (Python package)
         │
         ▼
    ┌─────────────────────────────────────────────────────┐
    │          PyO3 Bindings Layer (pyo3-stub-gen)        │
    └──────────────────────┬──────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┬────────────┐
         │                 │                 │            │
         ▼                 ▼                 ▼            ▼
    ┌─────────┐      ┌──────────┐     ┌──────────┐ ┌──────────┐
    │  thryd  │      │   cfg    │     │  logger  │ │constants │
    │(router) │      │ (config) │     │ (logging)│ │ (shared) │
    └────┬────┘      └────┬─────┘     └────┬─────┘ └──────────┘
         │                │                │
         ▼                ▼                ▼
    ┌─────────┐      ┌──────────┐     ┌──────────┐
    │  redb   │      │ figment  │     │  tracing │
    │ (cache) │      │ validator│     │  chrono  │
    └─────────┘      └──────────┘     └──────────┘

    thryd Dependencies:
    ├── async-openai      # OpenAI API client
    ├── reqwest           # HTTP client
    ├── tokio             # Async runtime
    ├── moka               # In-memory cache
    ├── redb              # Embedded DB for persistence
    ├── tiktoken-rs       # Token counting
    ├── dashmap           # Concurrent hashmap
    └── pyo3 (optional)   # Python bindings

Building Rust Crates
--------------------

.. code-block:: bash

    # Build all crates
    cargo build --release

    # Build specific crate
    cargo build -p thryd --release

    # Run tests for crates
    cargo test --workspace

    # Check formatting
    cargo fmt --check

Development Requirements
~~~~~~~~~~~~~~~~~~~~~~~~

- Rust 1.70+
- ``cargo`` package manager
- ``maturin`` for Python bindings (used in workspace)

PyO3 Integration
~~~~~~~~~~~~~~~~

Crates are exposed to Python via PyO3:

.. code-block:: rust

    use pyo3::prelude::*;

    #[pymodule]
    fn fabricatio_rust(_py: Python, m: &PyModule) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(llm_aask, m)?,)?;
        Ok(())
    }

Feature Flags Summary
~~~~~~~~~~~~~~~~~~~~~

===========  ============================================================
Crate        Features                                                     
===========  ============================================================
thryd        ``pyo3`` (Python bindings), ``pystub`` (stub generation)     
config       ``stubgen`` (Python stub generation)                        
logger       ``stubgen`` (Python stub generation)                        
stubgen      ``all``, ``core``, ``memory``, ``diff``, ...                
error-map    ``std``, ``git2``, ``epub-builder``, ``handlebars``,        
             ``tantivy``, ``mcp-manager``, ``thryd``, ...                
===========  ============================================================