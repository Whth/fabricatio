Development Setup
=================

Prerequisites
-------------

Before starting development, ensure you have:

- Python 3.12 or 3.13
- Rust toolchain (for building native extensions)
- UV package manager (recommended)

Quick Setup
-----------

Clone and set up the development environment:

.. code-block:: bash

   git clone https://github.com/Whth/fabricatio.git
   cd fabricatio
   make init
   make dev

Alternative Setup with UV
-------------------------

Using UV with maturin for development:

.. code-block:: bash

   git clone https://github.com/Whth/fabricatio.git
   cd fabricatio
   uvx --with-editable . maturin develop --uv -r

Development Commands
-------------------

**Initialize Development Environment:**

.. code-block:: bash

   make init

**Build in Development Mode:**

.. code-block:: bash

   make dev

**Run Tests:**

.. code-block:: bash

   make test
   # or
   make tests

**Fix Linting Issues:**

.. code-block:: bash

   make fix

**Build Distribution:**

.. code-block:: bash

   make bdist

**Generate Subpackages:**

.. code-block:: bash

   make rs    # Generate Rust subpackage
   make py    # Generate Python subpackage

Project Structure
----------------

The project follows a workspace structure with multiple packages:

- ``packages/`` - Individual fabricatio subpackages
- ``python/`` - Main Python source code
- ``src/`` - Rust source code
- ``examples/`` - Usage examples
- ``docs/`` - Documentation source
- ``tests/`` - Test suite

Testing
-------

Run the full test suite:

.. code-block:: bash

   make tests

For specific test configurations, check the ``pytest.ini_options`` in ``pyproject.toml``.

Code Quality
-----------

The project uses several tools for code quality:

- **Ruff** for linting and formatting
- **PyRight** for type checking
- **Pytest** for testing

Run linting and auto-fix issues:

.. code-block:: bash

   make fix

Building Documentation
---------------------

To build the documentation locally:

.. code-block:: bash

   cd docs
   make html

The documentation will be available in ``docs/build/html/``.

Debugging
---------

For debugging with visual tracing:

.. code-block:: bash

   # Install viztracer (included in dev dependencies)
   viztracer your_script.py

This will generate trace files that can be viewed in the VizTracer viewer.