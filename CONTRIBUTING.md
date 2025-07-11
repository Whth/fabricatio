# Contributing

---

Thank you for your interest in contributing to Fabricatio! We welcome contributions from the community. Please follow the steps below to get started:

1. **Fork** the repository on GitHub.

2. **Clone the Repository** to your local machine using:
   ```bash
   git clone https://github.com/<YOUR_USERNAME>/fabricatio.git
   cd fabricatio
   ```

3. **Install Dependencies** by running:
   ```bash
   make init
   ```

4. **Build the Package** in development mode:
   ```bash
   make dev
   ```

5. **Create** a new feature branch:
   ```bash
   git checkout -b feat/new-feature
   ```
6. *(Optional)* Generate a **Python** or **Rust** subpackage using the `cookiecutter` template:
   - For Rust:
     ```bash
     make rs    # generates a Rust subpackage
     ```
   - For Python:
     ```bash
     make py    # generates a Python subpackage
     ```
   > Templates: [Rust Template](https://github.com/Whth/fabricatio-maturin-template), [Python Template](https://github.com/Whth/fabricatio-purepython-template)

7. **Run Tests and Fix Linting Issues**:
   ```bash
   make tests  # run all tests
   make fix    # auto-fix linting issues
   ```

8. **Commit** your changes with a clear and descriptive commit message:
   ```bash
   git commit -am 'Add new feature'
   ```

9. **Push** your feature branch to your forked repository:
   ```bash
   git push origin feat/new-feature
   ```

10. **Open a Pull Request (PR)** on the original repository’s GitHub page. Make sure your PR follows the project's contribution guidelines and clearly explains the changes made.

We look forward to your contributions!

Happy coding 🚀
