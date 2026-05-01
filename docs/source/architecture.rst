Architecture Overview
=====================

Fabricatio is a Python LLM application framework built with an event-driven, multi-agent architecture. It leverages Rust (via PyO3) for performance-critical components, Handlebars for templating, and async Python for workflow orchestration.

Event-Driven Agent Architecture
--------------------------------

At its core, Fabricatio implements an event-driven agent pattern where roles respond to events through registered skills that map to workflow sequences:

.. mermaid::

   flowchart TD
      subgraph Role["Role (Agent)"]
         Event["Event\n(trigger)"]
         Skill["Skill\n(capability)"]
         WorkFlow["WorkFlow\n(step sequence)"]
         Task["Task\n(job unit)"]
         Action["Action\n(execute)"]

         Event --> Skill
         Skill --> WorkFlow
         Event --> Task
         WorkFlow --> Task
         Task -.->|input| Action
      end

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

.. mermaid::

   flowchart TD
      Root["fabricatio/"]

      subgraph PythonSrc["python/fabricatio/ (namespace package)"]
         Init["__init__.py"]
         subgraph Core["core/ (interfaces)"]
            RolePy["role.py"]
            EventPy["event.py"]
            SkillPy["skill.py"]
            WorkflowPy["workflow.py"]
            TaskPy["task.py"]
         end
         subgraph Caps["capabilities/"]
            UseLLM["use_llm.py"]
         end
      end

      subgraph Packages["packages/ (32 Python packages)"]
         subgraph Foundation["Foundation Layer (Required)"]
            PkgCore["fabricatio-core"]
            PkgCaps["fabricatio-capabilities"]
            PkgActions["fabricatio-actions"]
         end
         subgraph AgentLayer["Agent Layer (Orchestration)"]
            PkgAgent["fabricatio-agent"]
            PkgTeam["fabricatio-team"]
            PkgCapable["fabricatio-capable"]
            PkgMock["fabricatio-mock"]
         end
         subgraph ThinkMem["Thinking & Memory Layer"]
            PkgThinking["fabricatio-thinking"]
            PkgMemory["fabricatio-memory"]
            PkgDigest["fabricatio-digest"]
         end
         subgraph ContentProc["Content Processing Layer"]
            PkgImprove["fabricatio-improve"]
            PkgJudge["fabricatio-judge"]
            PkgDiff["fabricatio-diff"]
            PkgRule["fabricatio-rule"]
         end
         subgraph RAGLayer["RAG & Knowledge Layer"]
            PkgRAG["fabricatio-rag"]
            PkgMilvus["fabricatio-milvus"]
            PkgCheckpoint["fabricatio-checkpoint"]
         end
         subgraph GenLayer["Generation Layer"]
            PkgTypst["fabricatio-typst"]
            PkgNovel["fabricatio-novel"]
            PkgCharacter["fabricatio-character"]
            PkgYue["fabricatio-yue"]
            PkgAnki["fabricatio-anki"]
            PkgPlot["fabricatio-plot"]
         end
         subgraph ToolLayer["Tool & Integration Layer"]
            PkgTool["fabricatio-tool"]
            PkgWorkspace["fabricatio-workspace"]
            PkgWebUI["fabricatio-webui"]
         end
         subgraph UtilLayer["Utilities Layer"]
            PkgTranslate["fabricatio-translate"]
            PkgLocale["fabricatio-locale"]
            PkgTagging["fabricatio-tagging"]
            PkgQuestion["fabricatio-question"]
         end
         PkgLOD["fabricatio-lod (in development)"]
      end

      subgraph Crates["crates/ (15 Rust crates)"]
         subgraph CoreRust["Core Rust Crates"]
            CThryd["thryd (LLM router, PyO3)"]
            CConfig["fabricatio-config (PyO3)"]
            CLogger["fabricatio-logger (PyO3)"]
            CConst["fabricatio-constants"]
            CStubGen["fabricatio-stubgen"]
         end
         subgraph UtilRust["Utility Crates"]
            CUtils["utils"]
            CErrMap["error-mapping"]
            CTexConv["tex-convertor"]
            CSignify["signify"]
            CScanner["scanner"]
            CMCP["mcp-manager"]
            CMacro["macro-utils"]
            CDeck["deck_loader"]
         end
      end

      Config["pyproject.toml"]
      Cargo["Cargo.toml"]
      Just["Justfile"]

Rust Crates Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~

The Rust crates provide performance-critical functionality with Python bindings:

.. mermaid::

   flowchart TD
      Thryd["thryd (PyO3)\nLLM Request Router\n- Multi-provider routing (OpenAI, Azure)\n- Rate limiting (TPM/RPM)\n- Token counting (tiktoken)\n- Request caching (redb)\n- Embedding support"]
      Config["fabricatio-config (PyO3)\n- Multi-source config loading\n- Validation (validator)\n- SecretStr management\n- Python object creation"]
      Logger["fabricatio-logger"]
      StubGen["fabricatio-stubgen\n(pyto3-stub-gen)\nGenerates .pyi stubs for all PyO3 packages"]
      Constants["fabricatio-constants\n(no PyO3)"]

      Thryd --> Config
      Config --> Logger
      StubGen --> Config

Build System
------------

Fabricatio uses a hybrid Python/Rust build system:

.. mermaid::

   flowchart TD
      PyProject["pyproject.toml"] -->|uv workspace| Maturin["maturin (build)"]
      Maturin --> RustCrates["Rust crates (PyO3)\n- thryd\n- fabricatio-config\n- fabricatio-logger\n- ..."]
      Maturin --> Wheel["fabricatio.whl\n(Python wheel with native extensions)"]

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

.. mermaid::

   flowchart LR
      subgraph PyWorld["Python World"]
         FabricPkgs["fabricatio\n-core / -config\n-logger / -rag\n-thinking / -diff\n..."]
      end

      subgraph RustWorld["Rust World"]
         PyO3Mod["PyO3 Module\n- Native classes\n- async/await bindings\n- Error mapping"]
         RustCore["Rust Core Logic\n- thryd router\n- Config validation\n- Token counting\n- Request caching"]
         PyO3Mod --> RustCore
      end

      subgraph Integration["Integration Patterns"]
         P1["1. PyO3 generates Python classes from Rust impl"]
         P2["2. pyo3-stub-gen creates .pyi type stubs for IDE support"]
         P3["3. pythonize enables Rust-to-Python object conversion"]
         P4["4. async methods exposed via PyO3's async runtime"]
         P5["5. Secrets (API keys) use SecretStr to prevent logging leak"]
      end

      FabricPkgs -->|.pyi stubs| PyO3Mod

Dependency Resolution Flow
---------------------------

When Fabricatio processes an LLM request:

.. mermaid::

   flowchart TD
      User["User Code"] --> Role["Role.aask() / aask_structured()"]
      Role --> Core["fabricatio-core\n- Request building\n- Response parsing\n- Type validation (Pydantic)"]
      Core --> Config["fabricatio-config\n- Load config from env/TOML/pyproject\n- Validate all settings\n- Provide SecretStr for API keys"]
      Config --> Thryd["thryd crate\n- Provider routing (OpenAI/Azure/etc)\n- Rate limiting (TPM/RPM quotas)\n- Token counting (tiktoken)\n- Request/Response caching (redb)\n- Load balancing across deployments"]
      Thryd --> API["OpenAI-Compatible API\n(OpenAI, Anthropic, Azure, LocalAI)"]

Data Flow: RAG Pipeline
------------------------

.. mermaid::

   flowchart TD
      UQ["User Query"] --> RAG["MilvusRAG.retrieve()"]
      subgraph RAGPipeline["MilvusRAG.retrieve()"]
         Step1["1. Query embedding via TEI service\n(thryd - embedding provider)"]
         Step2["2. Vector search in Milvus DB\n- Similarity scoring\n- Top-k retrieval"]
         Step3["3. Context assembly\n- Document chunks + scores"]
         Step1 --> Step2 --> Step3
      end
      RAG --> RAGPipeline
      RAGPipeline --> LLM["Augmented Prompt --> LLM Completion"]

Data Flow: Multi-Agent Team Collaboration
-----------------------------------------

.. mermaid::

   flowchart TD
      Req["User Request"] --> Agent["fabricatio-agent\n- Decomposes request into subtasks\n- Creates specialized Role instances"]

      subgraph Team["Team Members"]
         A["Team Member A\n(digest)"]
         B["Team Member B\n(think)"]
         C["Team Member C\n(improve)"]
      end

      Agent --> A
      Agent --> B
      Agent --> C
      A --> Agg["Result Aggregation\n- Synthesize team member outputs\n- Final validation (fabricatio-judge)"]
      B --> Agg
      C --> Agg

Component Hierarchy
~~~~~~~~~~~~~~~~~~~

.. mermaid::

   flowchart TD
      UC["User Code"] --> Agent["fabricatio-agent"]
      Agent --> Thinking["fabricatio-thinking"]
      Agent --> Memory["fabricatio-memory"]
      Agent --> Judge["fabricatio-judge"]
      Thinking --> Caps["fabricatio-capabilities"]
      Memory --> RAG["fabricatio-rag"]
      Judge --> Improve["fabricatio-improve"]
      RAG --> Milvus["fabricatio-milvus"]
      Caps --> Core["fabricatio-core"]
      RAG --> Core
      Improve --> Core
      Core --> Thryd["thryd (Rust)"]
      Core --> Cfg["fabricatio-config (Rust)"]
      Core --> Log["fabricatio-logger"]

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

.. mermaid::

   flowchart TD
      C1["1. Call Arguments\ndirect parameter passing"]
      C2["2. Environment Variables\nFABRICATIO_* prefix"]
      C3["3. Local .env file"]
      C4["4. ./fabricatio.toml"]
      C5["5. ./pyproject.toml\n[tool.fabricatio]"]
      C6["6. ROAMING/fabricatio/fabricatio.toml"]
      C7["7. Built-in Defaults"]

      C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7

The ``ROAMING`` path is platform-dependent:

- **Linux**: ``$XDG_CONFIG_HOME`` or ``$HOME/.config/fabricatio``
- **macOS**: ``$HOME/Library/Application Support/fabricatio``
- **Windows**: ``%APPDATA%\fabricatio``
