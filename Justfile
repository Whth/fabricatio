# Configuration

SEHLL := "pwsh.exe"
DIST := "dist"
DATA := "extra"
PY := "3.13"
PY_TEMPLATE_URL := env("PY_TEMPLATE_URL", "https://github.com/Whth/fabricatio-purepython-template")
RS_TEMPLATE_URL := env("RS_TEMPLATE_URL", "https://github.com/Whth/fabricatio-maturin-template")
PACKAGES := "packages"

# Colors

RED := "\\033[0;31m"
GREEN := "\\033[0;32m"
YELLOW := "\\033[1;33m"
BLUE := "\\033[0;34m"
PURPLE := "\\033[0;35m"
CYAN := "\\033[0;36m"
NC := "\\033[0m"

# Format and fix code style.
fix:
    cargo fmt
    ruff format
    ruff check --fix --unsafe-fixes

# Build binary distribution (default target).
bdist dist_dir=DIST data_dir=DATA py_ver=PY:
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
publish dist_dir=DIST py_ver=PY:
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

# Create new Python package template.
py packages_dir=PACKAGES template_url=PY_TEMPLATE_URL:
    cookiecutter "{{ template_url }}" -o "{{ packages_dir }}" -v

# Create new Rust package template.
rs packages_dir=PACKAGES template_url=RS_TEMPLATE_URL:
    cookiecutter "{{ template_url }}" -o "{{ packages_dir }}" -v
