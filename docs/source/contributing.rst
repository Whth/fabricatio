Contributing
============

Thank you for your interest in contributing to Fabricatio! We welcome contributions from the community. Please follow the steps below to get started:

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

Submitting Changes
------------------

8. **Commit** your changes with a clear and descriptive commit message:

   .. code-block:: bash

      git commit -am 'Add new feature'

9. **Push** your feature branch to your forked repository:

   .. code-block:: bash

      git push origin feat/new-feature

10. **Open a Pull Request (PR)** on the original repository's GitHub page. Make sure your PR follows the project's contribution guidelines and clearly explains the changes made.

Guidelines
----------

- Follow the existing code style and conventions
- Write clear, descriptive commit messages
- Include tests for new functionality
- Update documentation as needed
- Ensure all tests pass before submitting

We look forward to your contributions!

Happy coding 🚀