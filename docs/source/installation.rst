Installation
============

Quick Installation
------------------

Install fabricatio with full capabilities:

.. code-block:: bash

   pip install fabricatio[full]

Or using UV (recommended):

.. code-block:: bash

   uv add fabricatio[full]

Selective Installation
----------------------

Install fabricatio with specific capabilities:

.. code-block:: bash

   # Install with only RAG and rule capabilities
   pip install fabricatio[rag,rule]

   # Or with uv
   uv add fabricatio[rag,rule]

Available Optional Dependencies
-------------------------------

Fabricatio supports various optional dependencies for different capabilities:

- ``anki``: Anki deck generation (fabricatio-anki)
- ``memory``: Memory management (fabricatio-memory)
- ``digest``: Content digestion (fabricatio-digest)
- ``rag``: Retrieval-Augmented Generation (fabricatio-rag)
- ``judge``: Judgment and evaluation (fabricatio-judge)
- ``rule``: Rule-based processing (fabricatio-rule)
- ``cli``: Command-line interface (typer-slim)
- ``typst``: Typst document generation (fabricatio-typst)
- ``improve``: Content improvement (fabricatio-improve)
- ``capabilities``: Core capabilities (fabricatio-capabilities)
- ``actions``: Action system (fabricatio-actions)
- ``question``: Question processing (fabricatio-question)
- ``tagging``: Content tagging (fabricatio-tagging)
- ``yue``: Yue language support (fabricatio-yue)
- ``tool``: Tool integration (fabricatio-tool)
- ``plot``: Plotting capabilities (fabricatio-plot)
- ``translate``: Translation services (fabricatio-translate)
- ``locale``: Localization support (fabricatio-locale)
- ``diff``: Diff utilities (fabricatio-diff)
- ``thinking``: Thinking/reasoning (fabricatio-thinking)

Development Installation
------------------------

For development, clone the repository and install in development mode:

.. code-block:: bash

   git clone https://github.com/Whth/fabricatio.git
   cd fabricatio
   make init
   make dev

Or using UV with maturin:

.. code-block:: bash

   git clone https://github.com/Whth/fabricatio.git
   cd fabricatio
   uvx --with-editable . maturin develop --uv -r

Building Distribution
---------------------

To build distribution packages:

.. code-block:: bash

   make bdist

Requirements
------------

- Python 3.12 or 3.13
- Rust toolchain (for development builds)
- UV package manager (recommended)
