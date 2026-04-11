Architecture Overview
=====================

Fabricatio is a Python LLM application framework built with an event-driven, multi-agent architecture. It leverages Rust (via PyO3) for performance-critical components, Handlebars for templating, and async Python for workflow orchestration.

Event-Driven Agent Architecture
--------------------------------

At its core, Fabricatio implements an event-driven agent pattern where roles respond to events through registered skills that map to workflow sequences:

.. code-block:: text

    ┌───────────────────────────────────────────────────────────────────────┐
    │                            Role (Agent)                              │
    │                                                                       │
    │  ┌──────────────┐    ┌──────────────┐    ┌─────────────────────────┐ │
    │  │    Event     │───▶│    Skill     │───▶│       WorkFlow          │ │
    │  │  (trigger)   │    │ (capability) │    │   (step sequence)       │ │
    │  └──────────────┘    └──────────────┘    └─────────────────────────┘ │
    │         │                                        │                   │
    │         │              ┌──────────────────────────┘                   │
    │         ▼              ▼                                               │
    │  ┌──────────────┐                                                ┌────┴───┐
    │  │    Task      │◀──────────────── (input)                       │ Action  │
    │  │  (job unit)  │                                                │(execute)│
    │  └──────────────┘                                                └────────┘
    │                                                                       │
    └───────────────────────────────────────────────────────────────────────┘

Core Concepts
~~~~~~~~~~~~~

**Role**
    The primary agent entity. A Role wraps a set of Skills and provides the interface for task delegation and LLM interaction.

**Event**
    A trigger mechanism using ``EventEmitter`` pattern. Events are identified by name and can be quickly instantiated via ``Event.quick_instantiate()``.

**Skill**
    A named capability that maps an Event to a WorkFlow. Skills are stored in a Role's skill registry.

**WorkFlow**
    A sequence of Actions to execute. WorkFlows can be synchronous (blocking) or asynchronous.

**Task**
    A unit of work assigned to a Role. Tasks carry input data and can be delegated to registered Skills.

**Action**
    The atomic execution unit. Actions implement the actual logic and can access LLM capabilities through mixins.

Project Structure
-----------------

Fabricatio uses a hybrid Python/Rust monorepo structure:

.. code-block:: text

    fabricatio/
    ├── python/                           # Python source (namespace package)
    │   └── fabricatio/
    │       ├── __init__.py
    │       ├── core/                    # Core interfaces
    │       │   ├── role.py
    │       │   ├── event.py
    │       │   ├── skill.py
    │       │   ├── workflow.py
    │       │   └── task.py
    │       ├── capabilities/            # Capability mixins
    │       │   └── use_llm.py
    │       └── ...
    │
    ├── packages/                        # Python packages (32 packages)
    │   │
    │   ├── Foundation Layer (Required)
    │   │   ├── fabricatio-core/          # Core types, event system, Role/Task/WorkFlow
    │   │   ├── fabricatio-capabilities/ # Extract, Propose, Rating, Task capabilities
    │   │   └── fabricatio-actions/      # File system & output actions
    │   │
    │   ├── Agent Layer (Orchestration)
    │   │   ├── fabricatio-agent/        # Multi-capability agent framework
    │   │   ├── fabricatio-team/         # Multi-agent collaboration
    │   │   ├── fabricatio-capable/      # Capability assessment
    │   │   └── fabricatio-mock/         # Testing utilities
    │   │
    │   ├── Thinking & Memory Layer
    │   │   ├── fabricatio-thinking/     # Sequential thinking with version control
    │   │   ├── fabricatio-memory/       # Long/short-term memory management
    │   │   └── fabricatio-digest/       # Requirement → task list parsing
    │   │
    │   ├── Content Processing Layer
    │   │   ├── fabricatio-improve/      # Content review & correction
    │   │   ├── fabricatio-judge/        # Evidence-based decision making
    │   │   ├── fabricatio-diff/         # Intelligent diff editing
    │   │   └── fabricatio-rule/         # Rule-based content processing
    │   │
    │   ├── RAG & Knowledge Layer
    │   │   ├── fabricatio-rag/          # Retrieval-augmented generation
    │   │   ├── fabricatio-milvus/       # Milvus vector database integration
    │   │   └── fabricatio-checkpoint/   # Version control & state management
    │   │
    │   ├── Generation Layer
    │   │   ├── fabricatio-typst/        # Academic writing with Typst
    │   │   ├── fabricatio-novel/       # Novel generation pipeline
    │   │   ├── fabricatio-character/   # Character creation
    │   │   ├── fabricatio-yue/         # Lyrics composition for YuE
    │   │   ├── fabricatio-anki/        # Anki deck generation
    │   │   └── fabricatio-plot/        # Data visualization
    │   │
    │   ├── Tool & Integration Layer
    │   │   ├── fabricatio-tool/         # Native Python tool execution
    │   │   ├── fabricatio-workspace/    # Isolated worktree development
    │   │   └── fabricatio-webui/       # Web user interface
    │   │
    │   ├── Utilities Layer
    │   │   ├── fabricatio-translate/   # Multi-language translation
    │   │   ├── fabricatio-locale/      # PO file localization
    │   │   ├── fabricatio-tagging/     # Data tagging & classification
    │   │   └── fabricatio-question/    # Interactive questioning
    │   │
    │   └── fabricatio-lod/             # LOD system (in development)
    │
    ├── crates/                         # Rust crates (15 crates)
    │   │
    │   ├── Core Rust Crates
    │   │   ├── thryd/                  # LLM request router (PyO3)
    │   │   ├── fabricatio-config/      # Configuration management (PyO3)
    │   │   ├── fabricatio-logger/      # Logging infrastructure (PyO3)
    │   │   ├── fabricatio-constants/   # Application constants
    │   │   └── fabricatio-stubgen/     # Python stub generation
    │   │
    │   └── Utility Crates
    │       ├── utils/                  # Shared utilities
    │       ├── error-mapping/          # Error type mapping
    │       ├── tex-convertor/          # TeX conversion
    │       ├── signify/                # Signing utilities
    │       ├── scanner/                # File scanning
    │       ├── mcp-manager/           # MCP protocol manager
    │       ├── macro-utils/            # Macro utilities
    │       └── deck_loader/           # Deck file loading
    │
    ├── pyproject.toml                  # Python workspace configuration
    ├── Cargo.toml                      # Rust workspace configuration
    └── Justfile                        # Build automation

Rust Crates Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~

The Rust crates provide performance-critical functionality with Python bindings:

.. code-block:: text

    ┌─────────────────────────────────────────────────────────────────┐
    │                    Rust Crates Architecture                     │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  ┌─────────────┐                                               │
    │  │   thryd     │  LLM Request Router                          │
    │  │  (PyO3)     │  ├── Multi-provider routing (OpenAI, Azure)  │
    │  └──────┬──────┘  ├── Rate limiting (TPM/RPM)                │
    │         │         ├── Token counting (tiktoken)               │
    │         │         ├── Request caching (redb)                   │
    │         │         └── Embedding support                        │
    │         │                                                ┌─────┴─────┐
    │         │         ┌──────────────────────────────┐      │ fabricatio│
    │         └────────▶│     fabricatio-config        │──────▶│  -logger  │
    │                   │        (PyO3)                 │      └───────────┘
    │                   ├── Multi-source config loading │
    │                   ├── Validation (validator)     │
    │                   └── SecretStr management        │
    │                   └── Python object creation     │
    │                                                              │
    │  ┌─────────────────────┐    ┌──────────────────────────┐   │
    │  │ fabricatio-stubgen  │    │  fabricatio-constants    │   │
    │  │  (pyo3-stub-gen)    │    │  (no PyO3)               │   │
    │  └──┬──────────────────┘    └──────────────────────────┘   │
    │     │  Generates .pyi stubs for all PyO3 packages         │
    └─────┴───────────────────────────────────────────────────────┘

Build System
------------

Fabricatio uses a hybrid Python/Rust build system:

.. code-block:: text

     pyproject.toml
          │ (uv workspace)
          ▼
    ┌──────────────────┐
    │  maturin (build)  │──────▶┬───────────────────────────┐
    └────────┬─────────┘       │   Rust crates (PyO3)     │
             │                  │   ├── thryd              │
             │                  │   ├── fabricatio-config  │
             │                  │   ├── fabricatio-logger  │
             │                  │   └── ...                │
             │                  └───────────────────────────┘
             │
             ▼
    ┌──────────────────┐
    │  fabricatio.whl   │  (Python wheel with native extensions)
    └──────────────────┘

Key Technologies
-----------------

- **PyO3**: Rust-Python bindings for native extension modules
- **maturin**: Build tool for Python extensions written in Rust
- **Handlebars.rs**: Rust template engine compiled to Python
- **async/await**: Full async execution with ``asyncio``
- **Pydantic V2**: Type validation and data models
- **uv**: Package management and workspace tooling
- **redb**: Embedded database for request caching

Rust-Python Integration
-----------------------

Fabricatio achieves tight Rust-Python integration through several mechanisms:

.. code-block:: text

    ┌─────────────────────────────────────────────────────────────────┐
    │                    Rust-Python Integration                      │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  Python World                    Rust World                     │
    │  ───────────                    ───────────                     │
    │                                                                 │
    │  ┌─────────────┐               ┌─────────────────────────┐    │
    │  │ fabricatio  │──────────────▶│  PyO3 Module             │    │
    │  │ -core       │  .pyi stubs   │  - Native classes       │    │
    │  │ -config     │               │  - async/await bindings │    │
    │  │ -logger     │               │  - Error mapping         │    │
    │  │ -rag        │               └─────────────────────────┘    │
    │  │ -thinking   │                        │                     │
    │  │ -diff       │                        │                     │
    │  │ ...         │                        ▼                     │
    │  └─────────────┘               ┌─────────────────────────┐    │
    │                                 │  Rust Core Logic         │    │
    │                                 │  - thryd router         │    │
    │                                 │  - Config validation    │    │
    │                                 │  - Token counting       │    │
    │                                 │  - Request caching      │    │
    │                                 └─────────────────────────┘    │
    │                                                                 │
    │  Integration Patterns:                                          │
    │  ────────────────────                                          │
    │  1. PyO3 generates Python classes from Rust impl                │
    │  2. pyo3-stub-gen creates .pyi type stubs for IDE support       │
    │  3. pythonize enables Rust→Python object conversion             │
    │  4. async methods exposed via PyO3's async runtime              │
    │  5. Secrets (API keys) use SecretStr to prevent logging leak    │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

Dependency Resolution Flow
---------------------------

When Fabricatio processes an LLM request:

.. code-block:: text

    User Code
        │
        ▼
    Role.aask() / aask_structured()
        │
        ▼
    ┌─────────────────────────────────────────┐
    │         fabricatio-core (Python)         │
    │  - Request building                      │
    │  - Response parsing                      │
    │  - Type validation (Pydantic)             │
    └─────────────────┬───────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────┐
    │      fabricatio-config (Rust+PyO3)       │
    │  - Load config from env/TOML/pyproject   │
    │  - Validate all settings                │
    │  - Provide SecretStr for API keys        │
    └─────────────────┬───────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────┐
    │           thryd crate (Rust)              │
    │  - Provider routing (OpenAI/Azure/etc)   │
    │  - Rate limiting (TPM/RPM quotas)         │
    │  - Token counting (tiktoken)              │
    │  - Request/Response caching (redb)        │
    │  - Load balancing across deployments     │
    └─────────────────┬───────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────┐
    │      OpenAI-Compatible API               │
    │  (OpenAI, Anthropic, Azure, LocalAI)     │
    └─────────────────────────────────────────┘

Data Flow: RAG Pipeline
------------------------

.. code-block:: text

    User Query
        │
        ▼
    ┌─────────────────────────────────────────┐
    │        MilvusRAG.retrieve()              │
    │  ┌─────────────────────────────────────┐ │
    │  │  1. Query embedding via TEI service │ │
    │  │     (thryd → embedding provider)    │ │
    │  └─────────────────────────────────────┘ │
    │                    │                      │
    │                    ▼                      │
    │  ┌─────────────────────────────────────┐ │
    │  │  2. Vector search in Milvus DB      │ │
    │  │     - Similarity scoring            │ │
    │  │     - Top-k retrieval               │ │
    │  └─────────────────────────────────────┘ │
    │                    │                      │
    │                    ▼                      │
    │  ┌─────────────────────────────────────┐ │
    │  │  3. Context assembly                │ │
    │  │     - Document chunks + scores      │ │
    │  └─────────────────────────────────────┘ │
    └─────────────────┬───────────────────────┘
                      │
                      ▼
    Augmented Prompt ──▶ LLM Completion

Data Flow: Multi-Agent Team Collaboration
-----------------------------------------

.. code-block:: text

    User Request
        │
        ▼
    ┌─────────────────────────────────────────┐
    │              fabricatio-agent            │
    │  - Decomposes request into subtasks     │
    │  - Creates specialized Role instances    │
    └─────────────────┬───────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │  Team   │  │  Team   │  │  Team   │
    │ Member A│  │ Member B│  │ Member C│
    │(digest) │  │(think)  │  │(improve)│
    └────┬────┘  └────┬────┘  └────┬────┘
         │            │            │
         └────────────┼────────────┘
                      ▼
    ┌─────────────────────────────────────────┐
    │         Result Aggregation               │
    │  - Synthesize team member outputs        │
    │  - Final validation (fabricatio-judge)  │
    └─────────────────────────────────────────┘

Component Hierarchy
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    ┌──────────────────────────────────────────────────────────────┐
    │                    Component Dependencies                     │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │   User Code                                                  │
    │      │                                                       │
    │      ▼                                                       │
    │   fabricatio-agent ──────────┐                              │
    │      │                       │                              │
    │      ├───────────────────────┼──────────────────────────┐   │
    │      │                       │                          │   │
    │      ▼                       ▼                          ▼   │
    │   fabricatio-              fabricatio-              fabricatio-│
    │   thinking                 memory                   judge    │
    │      │                       │                          │   │
    │      └───────────────────────┼──────────────────────────┘   │
    │                              │                              │
    │      ┌───────────────────────┼──────────────────────────┐   │
    │      │                       │                          │   │
    │      ▼                       ▼                          ▼   │
    │   fabricatio-capabilities   fabricatio-rag    fabricatio-improve │
    │      │                       │                          │   │
    │      │                       ▼                          │   │
    │      │                  fabricatio-milvus                │   │
    │      │                                                  │   │
    │      └───────────────────────┬──────────────────────────┘   │
    │                              │                              │
    │                              ▼                              │
    │   fabricatio-core ◀──────────┘                              │
    │      │                                                       │
    │      ▼                                                       │
    │   thryd (Rust) ── fabricatio-config (Rust) ── fabricatio-logger │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

Key Technologies
----------------

- **PyO3**: Rust-Python bindings for native extension modules
- **Handlebars.rs**: Rust template engine compiled to Python
- **async/await**: Full async execution with ``asyncio``
- **Pydantic V2**: Type validation and data models
- **uv**: Package management and workspace tooling
- **maturin**: Build tool for Python extensions written in Rust
- **redb**: Embedded key-value store for request caching
- **tiktoken**: Token counting for rate limit estimation

Configuration Priority
----------------------

Configuration values are resolved in the following order (highest to lowest priority):

.. code-block:: text

    1. Call Arguments (direct parameter passing)
           │
           ▼
    2. Environment Variables (FABRICATIO_* prefix)
           │
           ▼
    3. Local .env file
           │
           ▼
    4. ./fabricatio.toml
           │
           ▼
    5. ./pyproject.toml [tool.fabricatio]
           │
           ▼
    6. <ROAMING>/fabricatio/fabricatio.toml
           │
           ▼
    7. Built-in Defaults

The ``ROAMING`` path is platform-dependent:

- **Linux**: ``$XDG_CONFIG_HOME`` or ``$HOME/.config/fabricatio``
- **macOS**: ``$HOME/Library/Application Support/fabricatio``
- **Windows**: ``%APPDATA%\fabricatio``
