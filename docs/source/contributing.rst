Contributing
============

Thank you for your interest in contributing to Fabricatio! We welcome contributions from the community. Please follow the steps below to get started:

Design Philosophy
-----------------

Fabricatio follows an event-driven, capability-based architecture:

- **Composition over inheritance**: Mix capabilities (like ``UseLLM``, ``ProposeTask``) into Roles rather than deep class hierarchies
- **Python for ergonomics, Rust for performance**: User-facing APIs are Python; performance-critical components (token counting, JSON parsing, BibTeX management) are Rust
- **Tasks carry state**: Tasks accumulate context as they flow through workflows, enabling multi-step pipelines without global state
- **Cancellation-aware**: All async operations respect cancellation signals, making Fabricatio suitable for interactive and long-running agents

Getting Started
---------------

1. **Fork** the repository on GitHub.

2. **Clone the Repository** to your local machine:

   .. code-block:: bash

      git clone https://github.com/<YOUR_USERNAME>/fabricatio.git
      cd fabricatio

3. **Install Dependencies**:

   .. code-block:: bash

      make init

4. **Build the Package** in development mode:

   .. code-block:: bash

      make dev

5. **Create** a new feature branch:

   .. code-block:: bash

      git checkout -b feat/new-feature

Optional: Generate Subpackages
------------------------------

Generate a **Python** or **Rust** subpackage using the ``cookiecutter`` template:

- For Rust:

  .. code-block:: bash

     make rs    # generates a Rust subpackage

- For Python:

  .. code-block:: bash

     make py    # generates a Python subpackage

Templates: `Rust Template <https://github.com/Whth/fabricatio-maturin-template>`_, `Python Template <https://github.com/Whth/fabricatio-purepython-template>`_

Testing and Quality
-------------------

**Run Tests and Fix Linting Issues**:

.. code-block:: bash

   make tests  # run all tests
   make fix    # auto-fix linting issues

Python vs Rust Contributions
----------------------------

Fabricatio is a hybrid Python/Rust project:

- **Python packages** (``packages/``): User-facing APIs, workflows, actions, capabilities. Use ``pdm`` or ``uv`` for dependency management.
- **Rust crates** (``crates/``): Performance-critical components, exposed to Python via PyO3. Use ``maturin`` for building.
- **When to use Rust**: Token counting, JSON validation, BibTeX management, file I/O helpers — anything where Python overhead matters at scale.
- **When to use Python**: Workflow definitions, LLM integrations, action implementations — anything user-facing or requiring rapid iteration.

Submitting Changes
------------------

8. **Commit** your changes with a clear and descriptive commit message:

   .. code-block:: bash

      git commit -am 'Add new feature'

9. **Push** your feature branch to your forked repository:

   .. code-block:: bash

      git push origin feat/new-feature

10. **Open a Pull Request (PR)** on the original repository's GitHub page. Make sure your PR follows the project's contribution guidelines and clearly explains the changes made.

Contribution Guidelines
-----------------------

- Follow the existing code style and conventions (see :doc:`code-style`)
- Write clear, descriptive commit messages using Conventional Commits format
- Include tests for new functionality; test edge cases, not just happy paths
- Update documentation as needed — both docstrings and RST docs
- Ensure all tests pass before submitting (run ``make tests``)
- For Python contributions: type annotations required on all public functions
- For Rust contributions: all public items must be documented with ``///`` comments

Review Process
~~~~~~~~~~~~~~
1. Open a PR with a clear description of what changed and why
2. CI must pass (lint, type check, tests)
3. At least one maintainer review is required
4. Address all review comments before merge
5. Keep PRs focused: one concern per PR

We look forward to your contributions!

Happy coding 🚀