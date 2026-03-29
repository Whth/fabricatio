# Configuration

SEHLL := "pwsh.exe"
DIST := "dist"
DATA := "extra"
PY := "3.13"
PY_TEMPLATE_URL := env("PY_TEMPLATE_URL", "https://github.com/Whth/fabricatio-purepython-template.git")
RS_TEMPLATE_URL := env("RS_TEMPLATE_URL", "https://github.com/Whth/fabricatio-maturin-template.git")
PACKAGES := "packages"

# Colors

RED := "\\033[0;31m"
GREEN := "\\033[0;32m"
YELLOW := "\\033[1;33m"
BLUE := "\\033[0;34m"
PURPLE := "\\033[0;35m"
CYAN := "\\033[0;36m"
NC := "\\033[0m"

# Common Defaults

DEFAULT_AUTHOR := "UNK"
DEFAULT_LICENSE := "MIT"
DEFAULT_EMAIL := "example@mail.com"
DEFAULT_DESC := "An extension of fabricatio"

# Format and fix code style.
fix:
    cargo fmt
    ruff format
    ruff check --fix --unsafe-fixes

# Build binary distribution (default target).
bdist py_ver=PY dist_dir=DIST data_dir=DATA:
    mkdir -p "{{ dist_dir }}" "{{ data_dir }}"
    rm -rf "{{ dist_dir }}"/*
    uv run --only-dev subpackages.py -py "{{ py_ver }}" -dd "{{ dist_dir }}" --bdist

# Create necessary directories.
dirs dist_dir=DIST data_dir=DATA:
    mkdir -p "{{ dist_dir }}" "{{ data_dir }}"

# Build binary packages.
bins py_ver=PY dist_dir=DIST:
    mkdir -p "{{ dist_dir }}"
    uv run --only-dev subpackages.py -py "{{ py_ver }}" -dd "{{ dist_dir }}" --bins

# Build binary packages with dev dependencies.
dev py_ver=PY dist_dir=DIST:
    mkdir -p "{{ dist_dir }}"
    uv run --only-dev subpackages.py -py "{{ py_ver }}" -dd "{{ dist_dir }}" --dev

# Clean distribution directory.
clean_dist dist_dir=DIST:
    rm -rf "{{ dist_dir }}"/*

py_sync *arg:
    uv sync --extra full --group docs {{ arg }}

rs_sync *arg:
    cargo update --recursive --verbose {{ arg }}

# Run tests without installing dependencies.
test_raw:
    uv run --only-dev pytest python/tests packages/*/python/tests --cov

# Install full dependencies and run tests.
test: py_sync test_raw

# Build and prepare for publishing.
publish py_ver=PY dist_dir=DIST:
    mkdir -p "{{ dist_dir }}"
    rm -rf "{{ dist_dir }}"/*
    uv run --only-dev subpackages.py -py "{{ py_ver }}" -dd "{{ dist_dir }}" --publish

# Build documentation.
docs:
    make -C docs html

# Update dependencies.
update: rs_sync (py_sync "-U")

# Initialize development environment.
init py_ver=PY:
    uv sync -p "{{ py_ver }}" --no-install-project --only-dev

# 🐍✨ Create a New Pure Python Subpackage ✨🐍
py project_name description=DEFAULT_DESC author=DEFAULT_AUTHOR license=DEFAULT_LICENSE email=DEFAULT_EMAIL:
    @echo -e "{{ YELLOW }}🚀 Initializing new Python subpackage: fabricatio-{{ project_name }}...{{ NC }}"
    @echo -e "{{ BLUE }}ℹ️  Using template: {{ PY_TEMPLATE_URL }}{{ NC }}"
    @cookiecutter.exe {{ PY_TEMPLATE_URL }} \
      --no-input \
      -s \
      auther="{{ author }}" \
      license="{{ license }}" \
      email="{{ email }}" \
      project_name="{{ project_name }}" \
      description="{{ description }}" \
      -o packages
    @echo -e "{{ GREEN }}✅ Successfully created Python subpackage 'fabricatio-{{ project_name }}' in 'packages/' directory! 🎉{{ NC }}"
    @echo -e "{{ BLUE }}ℹ️  Displaying project structure for 'fabricatio-{{ project_name }}'...{{ NC }}"
    @ls ./packages/fabricatio-{{ project_name }}
    @echo -e "{{ BLUE }}ℹ️  Next steps: cd packages/fabricatio-{{ project_name }} and start coding! 💻{{ NC }}"

# 🦀🚀 Create a New Rust (Maturin) Subpackage 🚀🦀
rs project_name description=DEFAULT_DESC author=DEFAULT_AUTHOR license=DEFAULT_LICENSE email=DEFAULT_EMAIL:
    @echo -e "{{ YELLOW }}🛠️  Setting up new Rust (Maturin) subpackage: fabricatio-{{ project_name }}...{{ NC }}"
    @echo -e "{{ BLUE }}ℹ️  Using template: {{ RS_TEMPLATE_URL }}{{ NC }}"
    @cookiecutter.exe {{ RS_TEMPLATE_URL }} \
      --no-input \
      -s \
      auther="{{ author }}" \
      license="{{ license }}" \
      email="{{ email }}" \
      project_name="{{ project_name }}" \
      description="{{ description }}" \
      -o packages
    @echo -e "{{ GREEN }}✅ Successfully created Rust (Maturin) subpackage 'fabricatio-{{ project_name }}' in 'packages/' directory! 🎉{{ NC }}"
    @echo -e "{{ BLUE }}ℹ️  Displaying project structure for 'fabricatio-{{ project_name }}'...{{ NC }}"
    @ls ./packages/fabricatio-{{ project_name }}
    @echo -e "{{ BLUE }}ℹ️  Next steps: cd packages/fabricatio-{{ project_name }} and start coding with Rust and Maturin! 🦀🔥{{ NC }}"

# create a hbs template names `tname` as templates/built-in/
tm tname:
    @echo -e "{{ YELLOW }}📝 Creating new Handlebars template: {{ tname }}...{{ NC }}"
    @mkdir -p templates/built-in
    @touch templates/built-in/{{ tname }}.hbs
    @echo -e "{{ GREEN }}✅ Successfully created template 'templates/built-in/{{ tname }}.hbs'! 🎉{{ NC }}"
    @echo -e "{{ BLUE }}ℹ️  Next steps: Edit the template file and add your Handlebars content! ✨{{ NC }}"
    nvim templates/built-in/{{ tname }}.hbs

# remove a  hbs template names `tname` from the templates/built-in/
rtm tname:
    @echo -e "{{ YELLOW }}🗑️  Removing Handlebars template: {{ tname }}...{{ NC }}"
    @rm -f templates/built-in/{{ tname }}.hbs
    @echo -e "{{ GREEN }}✅ Successfully removed template 'templates/built-in/{{ tname }}.hbs'! 🎉{{ NC }}"
    @echo -e "{{ BLUE }}ℹ️  Template has been deleted from the built-in templates directory! 🧹{{ NC }}"

eg example_name:
    @echo -e "{{ YELLOW }}📝 Creating new example: {{ example_name }}...{{ NC }}"
    @mkdir -p examples/{{ example_name }}
    @touch examples/{{ example_name }}/{{ example_name }}.py
    @echo -e "{{ GREEN }}✅ Successfully created example 'examples/{{ example_name }}/{{ example_name }}.py'! 🎉{{ NC }}"

alias v := version
alias r := release

version:
    verbu packages/* crates/* -g || true

release:
    verbu packages/* crates/* . -r || true
