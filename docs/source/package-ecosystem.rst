Package Ecosystem Guide
======================

Fabricatio is organized as a monorepo with 31 Python packages and 4 Rust crates. This guide provides an overview of the ecosystem and helps you understand which packages to use for your use case.

Package Architecture
--------------------

The following diagram illustrates the high-level architecture and dependencies between packages:

.. code-block:: text

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        fabricatio (meta-package)                        │
    └─────────────────────────────────────────────────────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
    ┌─────────────┐            ┌─────────────┐            ┌─────────────────────┐
    │    Core     │            │   Rust      │            │     Integration     │
    │  Packages   │            │   Crates    │            │     Packages        │
    └─────────────┘            └─────────────┘            └─────────────────────┘
         │
    ┌────┴────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
    │         │        │        │        │        │        │        │        │
    ▼         ▼        ▼        ▼        ▼        ▼        ▼        ▼        ▼
  ┌────┐  ┌──────┐ ┌──────┐ ┌──────┐ ┌────┐  ┌──────┐ ┌──────┐ ┌────┐  ┌──────┐
  │Cap-│  │Memory│ │Tool  │ │Actions│ │Diff│  │Digest│ │Judge│  │Rule│  │Improve│
  │abil│  │      │ │      │ │      │ │    │  │      │ │      │  │    │  │      │
  └──┬─┘  └──────┘ └──────┘ └──┬───┘ └────┘ └──────┘ └──────┘ └────┘  └──┬──┘  └──┬───┘
     │                          │                                            │
     │    ┌─────────────────────┴────────────────────────┐                  │
     │    │                  Agent Framework               │                  │
     │    │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐ │                  │
     │    │  │Think-│ │Question│ │Team │ │Capable│ │     │ │                  │
     │    │  │ing   │ │      │ │      │ │      │ │     │ │                  │
     │    │  └──────┘ └──────┘ └──────┘ └──────┘ └─────┘ │                  │
     │    └───────────────────────────────────────────────┘                  │
     │                                                                       
     ▼                                                                       
  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
  │ RAG  │  │ Typst │  │Locale│  │Novel │  │Checkpoint│ │Anki │  │Plot  │
  └──┬───┘  └──────┘  └──┬───┘  └──┬───┘  └──────┘  └──────┘  └──────┘
     │                   │         │
     ▼                   │         │
  ┌──────┐               │         │
  │Milvus│               │         │
  └──────┘               │         │
                         ▼         ▼
                    ┌─────────┐ ┌──────┐
                    │Workspace│ │WebUI │
                    └─────────┘ └──────┘

Package Categories
------------------

Capability Packages
~~~~~~~~~~~~~~~~~~~

These packages provide domain-specific capabilities that can be mixed into your Roles:

+-------------------------------+-----------------------------------------------------------+
| Package                       | Purpose                                                   |
+===============================+===========================================================+
| ``fabricatio-capabilities``   | Core capabilities: Extract, Propose, Rating, Task         |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-rag``            | Retrieval-Augmented Generation with Milvus integration    |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-rule``           | Rule-based content validation, correction, and enforcement|
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-judge``          | Evidence-based decision making and content evaluation     |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-agent``          | Full AI agent framework with autonomous task fulfillment  |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-memory``         | Long-term and short-term memory management for agents     |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-actions``        | File system operations and output management actions      |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-improve``        | Content review, correction, and refinement                |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-digest``         | Raw requirement parsing and task list generation          |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-tagging``        | Intelligent data classification and tag management        |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-translate``      | Multi-language translation with batch processing          |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-typst``          | Academic content generation in Typst format               |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-tool``           | Dynamic tool discovery and native Python execution        |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-plot``           | Publication-quality matplotlib charts from dataframes     |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-locale``         | PO file-based internationalization support                |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-thinking``       | Version-controlled sequential reasoning process           |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-team``           | Multi-agent collaboration and role-based coordination     |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-character``      | Character profile generation for narrative content        |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-novel``          | End-to-end novel generation with character integration    |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-checkpoint``     | Git-like workflow state versioning and rollback           |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-milvus``         | Milvus vector database integration for RAG                |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-anki``           | AI-powered Anki flashcard deck generation                 |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-question``       | Strategic questioning for planning and info gathering     |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-yue``            | YuE music generation lyrics composition                   |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-diff``           | Intelligent diff-based code/text editing                  |
+-------------------------------+-----------------------------------------------------------+
| ``fabricatio-capable``        | Dynamic capability assessment and validation              |
+-------------------------------+-----------------------------------------------------------+

Integration Packages
~~~~~~~~~~~~~~~~~~~~

+---------------------------+----------------------------------------------------------+
| Package                   | Purpose                                                  |
+===========================+==========================================================+
| ``fabricatio-webui``      | Web-based user interface                                 |
+---------------------------+----------------------------------------------------------+
| ``fabricatio-workspace``   | Isolated development workspace management with git      |
+---------------------------+----------------------------------------------------------+
| ``fabricatio-lod``        | Level-based context compression *(in development)*       |
+---------------------------+----------------------------------------------------------+

Core Packages
~~~~~~~~~~~~~

+---------------------------+----------------------------------------------------------+
| Package                   | Purpose                                                  |
+===========================+==========================================================+
| ``fabricatio-core``       | Event system, Role framework, Task engine, Toolbox,      |
|                           | File utilities, Handlebars templating, Type models       |
+---------------------------+----------------------------------------------------------+
| ``fabricatio-mock``       | Testing utilities with mock LLM roles and fixtures       |
+---------------------------+----------------------------------------------------------+

Rust Crates
~~~~~~~~~~~

+---------------------------+----------------------------------------------------------+
| Crate                     | Purpose                                                  |
+===========================+==========================================================+
| ``fabricatio-config``     | Configuration loading and management                     |
+---------------------------+----------------------------------------------------------+
| ``fabricatio-logger``     | Structured logging utilities                             |
+---------------------------+----------------------------------------------------------+
| ``fabricatio-constants``  | Constants and shared values                              |
+---------------------------+----------------------------------------------------------+
| ``fabricatio-stubgen``    | Python stub file generation                              |
+---------------------------+----------------------------------------------------------+
| ``thryd``                 | Router engine: routing, caching, rate limiting           |
+---------------------------+----------------------------------------------------------+

Quick Reference by Use Case
---------------------------

**Simple Chat Agent**
    ``fabricatio-core`` + ``fabricatio-capabilities``

**RAG Application**
    ``fabricatio-rag`` or ``fabricatio-milvus``

**Code Review**
    ``fabricatio-core`` + ``fabricatio-capabilities`` + ``fabricatio-diff``

**Content Generation**
    ``fabricatio-core`` + ``fabricatio-improve`` + ``fabricatio-digest``

**Multi-Agent System**
    ``fabricatio-agent`` + ``fabricatio-team``

**Document Processing**
    ``fabricatio-core`` + ``fabricatio-rule`` + ``fabricatio-typst``

**Translation**
    ``fabricatio-translate`` + ``fabricatio-locale``

**Academic Writing**
    ``fabricatio-typst`` + ``fabricatio-rag``

**Novel Writing**
    ``fabricatio-novel`` + ``fabricatio-character``

**Flashcard Learning**
    ``fabricatio-anki`` + ``fabricatio-capabilities``

Package Dependencies Graph
--------------------------

.. code-block:: text

    fabricatio (meta-package)
    │
    ├── fabricatio-core ──────────────────────────────────────┬──▶ thryd (Rust)
    │   (Event system, Role framework, Task engine, Toolbox)   │
    │                                                         │
    ├── fabricatio-capabilities ─────────────────────────────┴──▶ fabricatio-core
    │   (Extract, Propose, Rating, Task)                        │
    │                                                         │
    ├── fabricatio-rag ───────────────────────────────────────▶ fabricatio-core
    │   (Semantic search, Milvus integration, TEI support)      │    + pymilvus
    │                                                         │
    ├── fabricatio-milvus ────────────────────────────────────▶ fabricatio-rag
    │   (Vector database integration)                         │    + pymilvus
    │                                                         │
    ├── fabricatio-agent ─────────────────────────────────────▶ fabricatio-core
    │   (Autonomous task fulfillment)                        │    + fabricatio-digest
    │                                                         │    + fabricatio-memory
    │                                                         │    + fabricatio-improve
    │                                                         │    + fabricatio-rule
    │                                                         │    + fabricatio-judge
    │                                                         │    + fabricatio-capabilities
    │                                                         │    + fabricatio-diff
    │                                                         │    + fabricatio-thinking
    │                                                         │    + fabricatio-question
    │                                                         │    + fabricatio-tool
    │                                                         │    + fabricatio-team
    │                                                         │    + fabricatio-capable
    │                                                         │
    ├── fabricatio-actions ───────────────────────────────────▶ fabricatio-core
    │   (File system operations)                             │    + fabricatio-capabilities
    │                                                         │
    ├── fabricatio-workspace ───────────────────────────────▶ fabricatio-core
    │   (Isolated development environments)                  │    + git
    │                                                         │
    ├── fabricatio-webui ────────────────────────────────────▶ fabricatio-core
    │   (Web interface)                                      │    + grpcio
    │                                                         │
    ├── fabricatio-typst ────────────────────────────────────▶ fabricatio-core
    │   (Academic content generation)                       │    + fabricatio-rag
    │                                                         │    + fabricatio-capabilities
    │                                                         │
    ├── fabricatio-locale ──────────────────────────────────▶ fabricatio-core
    │   (PO file internationalization)                      │    + fabricatio-translate
    │                                                         │
    ├── fabricatio-novel ───────────────────────────────────▶ fabricatio-core
    │   (Novel generation)                                   │    + fabricatio-character
    │                                                         │
    ├── fabricatio-rule ────────────────────────────────────▶ fabricatio-core
    │   (Content validation)                                 │    + fabricatio-improve
    │                                                         │    + fabricatio-judge
    │                                                         │    + fabricatio-capabilities
    │                                                         │
    ├── fabricatio-improve ─────────────────────────────────▶ fabricatio-core
    │   (Content correction)                                 │    + fabricatio-capabilities
    │                                                         │
    ├── fabricatio-capable ─────────────────────────────────▶ fabricatio-core
    │   (Capability assessment)                              │    + fabricatio-tool
    │                                                         │    + fabricatio-judge
    │                                                         │
    ├── fabricatio-diff ────────────────────────────────────▶ fabricatio-core
    │   (Diff-based editing)                                 │
    │                                                         │
    ├── fabricatio-digest ─────────────────────────────────▶ fabricatio-core
    │   (Requirement parsing)                               │
    │                                                         │
    ├── fabricatio-judge ──────────────────────────────────▶ fabricatio-core
    │   (Evidence-based decisions)                           │
    │                                                         │
    ├── fabricatio-memory ─────────────────────────────────▶ fabricatio-core
    │   (Memory management)                                 │
    │                                                         │
    ├── fabricatio-thinking ───────────────────────────────▶ fabricatio-core
    │   (Sequential reasoning)                             │
    │                                                         │
    ├── fabricatio-team ───────────────────────────────────▶ fabricatio-core
    │   (Multi-agent coordination)                          │
    │                                                         │
    ├── fabricatio-tool ───────────────────────────────────▶ fabricatio-core
    │   (Tool execution)                                    │
    │                                                         │
    ├── fabricatio-character ──────────────────────────────▶ fabricatio-core
    │   (Character generation)                             │
    │                                                         │
    ├── fabricatio-checkpoint ─────────────────────────────▶ fabricatio-core
    │   (Version control)                                   │
    │                                                         │
    ├── fabricatio-anki ───────────────────────────────────▶ fabricatio-core
    │   (Flashcard generation)                             │
    │                                                         │
    ├── fabricatio-question ──────────────────────────────▶ fabricatio-core
    │   (Strategic questioning)                            │
    │                                                         │
    ├── fabricatio-yue ────────────────────────────────────▶ fabricatio-core
    │   (Lyrics composition)                               │
    │                                                         │
    ├── fabricatio-tagging ───────────────────────────────▶ fabricatio-core
    │   (Data classification)                              │
    │                                                         │
    ├── fabricatio-translate ─────────────────────────────▶ fabricatio-core
    │   (Translation)                                       │
    │                                                         │
    ├── fabricatio-plot ───────────────────────────────────▶ fabricatio-core
    │   (Chart generation)                                 │    + matplotlib
    │                                                         │
    └── fabricatio-mock ──────────────────────────────────▶ fabricatio-core
        (Testing utilities)                                 │

Installation Patterns
---------------------

**Minimal (core only)**
    ``pip install fabricatio``

**With RAG**
    ``pip install fabricatio[rag]``

**With Milvus vector database**
    ``pip install fabricatio[milvus]``

**With all capabilities**
    ``pip install fabricatio[full]``

**Selective**
    ``pip install fabricatio[rag,rule,judge,capabilities,agent]``

**Development workspace**
    ``pip install fabricatio[workspace,checkpoint]``

**Academic writing**
    ``pip install fabricatio[typst,rag]``

Package Development
-------------------

Each package follows a consistent structure:

::

    packages/
    └── fabricatio-{name}/
        ├── README.md
        ├── pyproject.toml
        ├── src/
        │   └── fabricatio_{name}/
        │       ├── __init__.py
        │       └── ...
        └── python/
            └── fabricatio_{name}/  # Pure Python fallback
                └── ...

Package authors can use the ``make py`` command to generate new Python subpackages from templates.

External Dependencies Summary
-----------------------------

- ``fabricatio-rag`` — ``pymilvus>=2.5.4``, TEI service
- ``fabricatio-milvus`` — ``pymilvus>=2.5.4``, Milvus database
- ``fabricatio-plot`` — ``matplotlib``
- ``fabricatio-workspace`` — ``git``
- ``fabricatio-webui`` — ``grpcio``, gRPC services
