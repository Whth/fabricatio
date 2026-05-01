Rust Crates
===========

Fabricatio's performance-critical components are implemented in Rust as independent crates,
providing high-performance routing, caching, and system integration for the Python ecosystem.

thryd
-----

**Router Engine** - High-performance LLM request routing with intelligent caching and rate limiting.

.. mermaid::

   flowchart TD
   thryd["thryd/"]
   src["src/"]
   readme["README.md"]
   thryd --> src
   thryd --> readme
   src --> lib["lib.rs - Main entry, exports"]
   src --> router["router.rs - Core routing engine"]
   src --> cache["cache.rs - redb-based persistent cache"]
   src --> rate_limiter["rate_limiter.rs - TPM/RPM sliding window limiter"]
   src --> provider["provider.rs - Provider trait & OpenAI-compatible impl"]
   src --> model["model.rs - Completion & embedding models"]
   src --> deployment["deployment.rs - Deployment with usage tracking"]
   src --> tracker["tracker.rs - Token usage tracking (tiktoken)"]
   src --> error["error.rs - ThrydError enum"]
   src --> constants["constants.rs - Rate limiting constants"]

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

.. mermaid::

   flowchart TD
   subgraph thryd["thryd Router"]
      PM["Provider Manager"]
      Cache["Cache (redb)"]
      RL["Rate Limiter\n(TPM/RPM Sliding)"]
      Router["Router Engine"]
      PM --> Router
      Cache --> Router
      RL --> Router
      Router --> D1["Deployment (gpt-4)\nRPM: 60 / TPM: 100k"]
      Router --> D2["Deployment (gpt-3.5)\nRPM: 1000 / TPM: 200k"]
      Router --> D3["Deployment (claude-3)\nRPM: 20 / TPM: 80k"]
   end
   D1 --> APIs["LLM Provider APIs\nOpenAI / Anthropic / ..."]
   D2 --> APIs
   D3 --> APIs

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

.. mermaid::

   flowchart LR
   subgraph window["Sliding Window Rate Limiter (60 buckets x 60s)"]
      direction LR
      B0["Bucket 0 (oldest, exits)"] --> B1["Bucket 1"] --> Bdots["..."] --> B59["Bucket 59 (newest, enters)"]
   end
   Request["Incoming Request"] --> B59
   Note["Each request increments a bucket based on timestamp.\nRPM/TPM = sum of all buckets in window."]

fabricatio-config
-----------------

**Configuration Management** - Multi-source configuration loading with validation.

.. mermaid::

   flowchart TD
   cfg["fabricatio-config/"]
   src["src/"]
   readme["README.md"]
   cfg --> src
   cfg --> readme
   src --> lib["lib.rs - Config struct, Python bindings"]
   src --> loader["loader.rs - Figment-based config loading"]
   src --> env["env.rs - Environment variable parsing"]
   src --> validation["validation.rs - Validator trait impls"]
   src --> secret["secret.rs - SecretStr for API keys"]

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

.. mermaid::

   flowchart TD
   config["fabricatio.toml"]
   debug["debug\nlog_level = DEBUG"]
   llm["llm\nsend_to, max_completion_tokens,\nstream, temperature, top_p"]
   routing["routing\nproviders, completion_deployments"]
   config --> debug
   config --> llm
   config --> routing

fabricatio-logger
-----------------

**Structured Logging** - Performance-optimized logging with loguru-style formatting.

.. mermaid::

   flowchart TD
   logger["fabricatio-logger/"]
   src["src/"]
   readme["README.md"]
   logger --> src
   logger --> readme
   src --> lib["lib.rs - Main entry, init functions"]
   src --> formatter["formatter.rs - Custom FormatEvent impl"]
   src --> writer["writer.rs - Output handling, rotation"]

Features:

- **Loguru-Style Format**: ANSI colors, module/line context
- **Log Rotation**: never, minutely, hourly, daily options
- **Thread-Safe**: Global logger with Tokio runtime support
- **Python Integration**: Auto-configure from Python settings

Log Levels: TRACE < DEBUG < INFO < WARN < ERROR

fabricatio-constants
--------------------

**Shared Constants** - Application-wide path and variable definitions.

.. mermaid::

   flowchart TD
   constants["fabricatio-constants/"]
   src["src/"]
   readme["README.md"]
   constants --> src
   constants --> readme
   src --> lib["lib.rs - Exports all constants"]
   src --> paths["paths.rs - Platform-aware path constants"]
   src --> limits["limits.rs - Rate/limit constants"]
   src --> defaults["defaults.rs - Default values"]

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

.. mermaid::

   flowchart TD
   stubgen["fabricatio-stubgen/"]
   src["src/"]
   readme["README.md"]
   stubgen --> src
   stubgen --> readme
   src --> lib["lib.rs - Main entry"]
   src --> generator["generator.rs - Stub generation logic"]
   src --> templates["templates.rs - Stub templates"]

Features:

- **Automatic Discovery**: Scans packages for PyO3 bindings
- **Type Annotations**: Full signatures in generated ``.pyi`` files
- **Multi-Package**: Handles all fabricatio packages in one run
- **Opt-In**: Enabled via ``stubgen`` feature flag

Additional Crates
-----------------

**tex-convertor** - LaTeX to Typst conversion

.. mermaid::

   flowchart TD
   crate["tex-convertor/"]
   lib["src/lib.rs - regex + tex2typst-rs"]
   crate --> lib

**scanner** - Python package filesystem scanner

.. mermaid::

   flowchart TD
   crate["scanner/"]
   lib["src/lib.rs - pep508_rs, walkdir, rayon"]
   crate --> lib

**error-mapping** - Error type mapping between Rust/Python

.. mermaid::

   flowchart TD
   crate["error-mapping/"]
   lib["src/lib.rs - cfg-if feature gating, various deps"]
   crate --> lib

**mcp-manager** - Model Context Protocol server management

.. mermaid::

   flowchart TD
   crate["mcp-manager/"]
   lib["src/lib.rs - rmcp client, tokio async"]
   crate --> lib

**deck_loader** - Anki deck file loading/generation

.. mermaid::

   flowchart TD
   crate["deck_loader/"]
   lib["src/lib.rs - genanki-rs-rev, csv, yaml"]
   crate --> lib

**signify** (v0.1.1) - JSON Schema to Python signature converter

.. mermaid::

   flowchart TD
   crate["signify/"]
   lib["src/lib.rs - heck, serde, serde_json"]
   crate --> lib

Features:

- ``schema_to_signature(&Value) -> String`` - Python function signature from JSON Schema
- ``schema_to_docstring_args(&Value) -> String`` - Google-style Args section
- Snake_case conversion of property names
- Type mapping: string, number, integer, boolean, array, object
- Required/optional parameter ordering with ``Optional[T]`` wrapping

**macro-utils** (v0.1.1) - Procedural macro utilities

.. mermaid::

   flowchart TD
   crate["macro-utils/"]
   lib["src/lib.rs - quote, syn (proc-macro crate)"]
   crate --> lib

Features:

- Single derive macro: ``TemplateDefault``
- Generates ``Default`` impls for structs with ``_template`` suffixed fields
- Supports optional ``#[suffix(...)]`` attribute for custom suffixes

**utils** (v0.1.2) - Shared utility functions

.. mermaid::

   flowchart TD
   crate["utils/"]
   lib["src/lib.rs - No external dependencies"]
   crate --> lib

Features:

- Single public function: ``mwrap<T>(item: T) -> Arc<Mutex<T>>``
- Thread-safe shared mutable ownership wrapper
- Combines Arc (atomic reference counting) with Mutex (mutual exclusion)

Rust Crate Dependencies
-----------------------

.. mermaid::

   flowchart TD
   py["fabricatio (Python package)"]
   subgraph pyo3["PyO3 Bindings Layer (pyo3-stub-gen)"]
      thryd["thryd (router)"]
      cfg["cfg (config)"]
      logger["logger (logging)"]
      constants["constants (shared)"]
   end
   py --> pyo3
   thryd --> redb["redb (cache)"]
   cfg --> figment["figment + validator"]
   logger --> tracing["tracing + chrono"]
   subgraph thryd_deps["thryd Dependencies"]
      async_openai["async-openai - OpenAI API client"]
      reqwest_lib["reqwest - HTTP client"]
      tokio_lib["tokio - Async runtime"]
      moka_lib["moka - In-memory cache"]
      redb_lib["redb - Embedded DB for persistence"]
      tiktoken["tiktoken-rs - Token counting"]
      dashmap["dashmap - Concurrent hashmap"]
      pyo3_opt["pyo3 - Python bindings (optional)"]
   end
   thryd --> thryd_deps

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