Package Ecosystem Guide
=========================

Fabricatio is organized as a monorepo with 31 Python packages and 13 Rust crates. This guide provides an overview of the ecosystem and helps you understand which packages to use for your use case.

Package Architecture
--------------------

The following diagram illustrates the high-level architecture and dependencies between packages:

.. mermaid::

   flowchart TD
       META["fabricatio<br/>(meta-package)"]
       subgraph CORE_LAYER [Core Packages]
           CORE["fabricatio-core"]
           CAP["Capabilities"]
           MEM["Memory"]
           TOOL["Tool"]
           ACTIONS["Actions"]
           DIFF["Diff"]
           DIGEST["Digest"]
           JUDGE["Judge"]
           RULE["Rule"]
           IMPROVE["Improve"]
           subgraph AGENT [Agent Framework]
               THINK["Thinking"]
               QUESTION["Question"]
               TEAM["Team"]
               CAPABLE["Capable"]
           end
       end
       subgraph RUST_LAYER [Rust Crates]
           RUST["Rust Crates"]
       end
       subgraph INT_LAYER [Integration Packages]
           RAG["RAG"]
           MILVUS["Milvus"]
           TYPST["Typst"]
           LOCALE["Locale"]
           NOVEL["Novel"]
           CHECKPOINT["Checkpoint"]
           ANKI["Anki"]
           PLOT["Plot"]
           WORKSPACE["Workspace"]
           WEBUI["WebUI"]
       end
       META --> CORE_LAYER
       META --> RUST_LAYER
       META --> INT_LAYER
       CAP --> AGENT
       ACTIONS --> AGENT
       RAG --> MILVUS
       NOVEL --> WEBUI
       NOVEL --> WORKSPACE

Package Categories
------------------

Capability Packages
~~~~~~~~~~~~~~~~~~~

These packages provide domain-specific capabilities that can be mixed into your Roles:

.. note::

   The ``sphinxcontrib-mermaid`` package that renders these diagrams is `seeking new maintainers <https://github.com/mgaitan/sphinxcontrib-mermaid/issues/148>`_. Consider contributing if you're interested.

.. mermaid::

   %%{init: {'themeVariables': {'fontFamily': 'monospace'}}}%%
   erDiagram
       Package {
           string fabricatio-capabilities "Core capabilities: Extract, Propose, Rating, Task"
           string fabricatio-rag "Retrieval-Augmented Generation with Milvus integration"
           string fabricatio-digest "Raw requirement parsing and task list generation"
           string fabricatio-tagging "Intelligent data classification and tag management"
           string fabricatio-translate "Multi-language translation with batch processing"
           string fabricatio-typst "Academic content generation in Typst format"
           string fabricatio-tool "Dynamic tool discovery and native Python execution"
           string fabricatio-plot "Publication-quality matplotlib charts from dataframes"
           string fabricatio-locale "PO file-based internationalization support"
           string fabricatio-thinking "Version-controlled sequential reasoning process"
           string fabricatio-team "Multi-agent collaboration and role-based coordination"
           string fabricatio-character "Character profile generation for narrative content"
           string fabricatio-novel "End-to-end novel generation with character integration"
           string fabricatio-checkpoint "Git-like workflow state versioning and rollback"
           string fabricatio-milvus "Milvus vector database integration for RAG"
           string fabricatio-anki "AI-powered Anki flashcard deck generation"
           string fabricatio-question "Strategic questioning for planning and info gathering"
           string fabricatio-yue "YuE music generation lyrics composition"
           string fabricatio-diff "Intelligent diff-based code/text editing"
           string fabricatio-capable "Dynamic capability assessment and validation"
           string fabricatio-rule "Rule-based content validation, correction, and enforcement"
           string fabricatio-judge "Evidence-based decision making and content evaluation"
           string fabricatio-agent "Full AI agent framework with autonomous task fulfillment"
           string fabricatio-memory "Long-term and short-term memory management for agents"
           string fabricatio-actions "File system operations and output management actions"
           string fabricatio-improve "Content review, correction, and refinement"
       }

Integration Packages
~~~~~~~~~~~~~~~~~~~~

.. mermaid::

   %%{init: {'themeVariables': {'fontFamily': 'monospace'}}}%%
   erDiagram
       "Integration Packages" {
           string fabricatio-webui "Web-based user interface"
           string fabricatio-workspace "Isolated development workspace management with git"
           string fabricatio-lod "Level-based context compression *(in development)*"
       }

Core Packages
~~~~~~~~~~~~~

.. mermaid::

   %%{init: {'themeVariables': {'fontFamily': 'monospace'}}}%%
   erDiagram
       "Core Packages" {
           string fabricatio-core "Event system, Role framework, Task engine, Toolbox, File utilities, Handlebars templating, Type models"
           string fabricatio-mock "Testing utilities with mock LLM roles and fixtures"
       }

Rust Crates
~~~~~~~~~~~

.. mermaid::

   %%{init: {'themeVariables': {'fontFamily': 'monospace'}}}%%
   erDiagram
       "Rust Crates" {
           string fabricatio-config "Configuration loading and management"
           string fabricatio-logger "Structured logging utilities"
           string fabricatio-constants "Constants and shared values"
           string fabricatio-stubgen "Python stub file generation"
           string thryd "Router engine: routing, caching, rate limiting"
           string utils "Shared utility functions (Arc/Mutex wrapper)"
           string macro-utils "Procedural macro utilities (TemplateDefault derive)"
       }

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

.. mermaid::

   %%{init: {'themeVariables': {'fontFamily': 'monospace'}}}%%
   flowchart TB
       M["fabricatio<br/>(meta-package)"]

       subgraph Core ["|"]
           C["fabricatio-core<br/>Event system, Role framework,<br/>Task engine, Toolbox"]
           TH["thryd<br/>(Rust)"]
       end

       subgraph Capabilities
           CAP["fabricatio-capabilities<br/>Extract, Propose, Rating, Task"]
       end

       subgraph RAG
           RAG["fabricatio-rag<br/>Semantic search, Milvus integration, TEI"]
           M["fabricatio-milvus<br/>Vector database integration"]
           PM["pymilvus"]
       end

       subgraph Agent
           AG["fabricatio-agent<br/>Autonomous task fulfillment"]
           DIG["fabricatio-digest"]
           MEM["fabricatio-memory"]
           IMP["fabricatio-improve"]
           RULE["fabricatio-rule"]
           JUD["fabricatio-judge"]
           CAP2["fabricatio-capabilities"]
           DIFF["fabricatio-diff"]
           THINK["fabricatio-thinking"]
           Q["fabricatio-question"]
           TOOL["fabricatio-tool"]
           TEAM["fabricatio-team"]
           CAPABLE["fabricatio-capable"]
       end

       subgraph Integrations
           ACT["fabricatio-actions<br/>File system operations"]
           WS["fabricatio-workspace<br/>Isolated dev environments"]
           WEB["fabricatio-webui<br/>Web interface"]
           TY["fabricatio-typst<br/>Academic content generation"]
           LOC["fabricatio-locale<br/>PO file i18n"]
           NL["fabricatio-novel<br/>Novel generation"]
           CHAR["fabricatio-character"]
           CHK["fabricatio-checkpoint<br/>Version control"]
           ANKI["fabricatio-anki<br/>Flashcard generation"]
           QST["fabricatio-question"]
           YUE["fabricatio-yue<br/>Lyrics composition"]
           TAG["fabricatio-tagging<br/>Data classification"]
           TRANS["fabricatio-translate<br/>Translation"]
           PLOT["fabricatio-plot<br/>Data visualization"]
           LOD["fabricatio-lod<br/>Context compression"]
       end

       M --> C
       C --> TH
       CAP -.-> C
       RAG -.-> C
       RAG -.-> PM
       M -.-> PM

       AG --> C
       AG --> DIG & MEM & IMP & RULE & JUD & CAP2 & DIFF & THINK & Q & TOOL & TEAM & CAPABLE

       ACT --> C
       ACT --> CAP2

       WS --> C
       WS -.-> G[git]

       WEB --> C
       WEB -.-> GRPC[grpcio]

       TY --> C
       TY -.-> RAG & CAP

       LOC --> C
       LOC -.-> TRANS

       NL --> C
       NL -.-> CHAR

       RULE -.-> IMP & JUD & CAP2
       IMP -.-> CAP2
       CAPABLE -.-> TOOL & JUD

       M -.-> RAG
       RAG -.-> M
       M -.-> AG
