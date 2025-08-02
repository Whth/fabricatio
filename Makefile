DIST:=dist
DATA:=extra
PY:=3.13

PY_TEMPLATE_URL:=https://github.com/Whth/fabricatio-purepython-template

RS_TEMPLATE_URL:=https://github.com/Whth/fabricatio-maturin-template

PACKAGES:=packages

# Colors
RED:=\033[0;31m
GREEN:=\033[0;32m
YELLOW:=\033[1;33m
BLUE:=\033[0;34m
PURPLE:=\033[0;35m
CYAN:=\033[0;36m
NC:=\033[0m # No Color

all:bdist

dirs:
	mkdir -p $(DIST) $(DATA)

bins: dirs
	uv run --only-dev subpackages.py -py $(PY) -dd $(DIST) --bins

dev: dirs
	uv run --only-dev subpackages.py -py $(PY) -dd $(DIST) --bins --dev

clean_dist:
	rm -rf $(DIST)/*

bdist: dirs clean_dist
	uv run --only-dev subpackages.py -py $(PY) -dd $(DIST) --bdist

test_raw:
	uv run --only-dev pytest python/tests packages/*/python/tests --cov

test: dev
	uv sync --extra full
	make test_raw

publish: dirs clean_dist
	uv run --only-dev subpackages.py -py $(PY) -dd $(DIST) --publish

docs:
	make -C docs html

update:
	cargo update --recursive --verbose && uv sync --extra full --group docs -U

init:
	uv sync -p $(PY) --no-install-project  --only-dev

fix:
	cargo fmt
	ruff format
	ruff check --fix --unsafe-fixes

py:
	cookiecutter $(PY_TEMPLATE_URL) -o $(PACKAGES) -v

rs:
	cookiecutter $(RS_TEMPLATE_URL) -o $(PACKAGES) -v

help:
	@echo -e "\
	$(CYAN)🚀 Available Commands:$(NC)\n\
	\n\
	$(GREEN)make$(NC) $(YELLOW)all$(NC)           $(PURPLE)# Build binary distribution (default target) 📦$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)dirs$(NC)          $(PURPLE)# Create necessary directories 📁$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)bins$(NC)          $(PURPLE)# Build binary packages 🛠️$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)dev$(NC)           $(PURPLE)# Build binary packages with dev dependencies 👨‍💻$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)clean_dist$(NC)    $(PURPLE)# Clean distribution directory 🧹$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)bdist$(NC)         $(PURPLE)# Build binary distribution 📦$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)test_raw$(NC)      $(PURPLE)# Run tests without installing dependencies 🧪$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)test$(NC)          $(PURPLE)# Install full dependencies and run tests 🧪$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)publish$(NC)       $(PURPLE)# Build and prepare for publishing 🚀$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)docs$(NC)          $(PURPLE)# Build documentation 📚$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)update$(NC)        $(PURPLE)# Update dependencies 🔧$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)init$(NC)          $(PURPLE)# Initialize development environment 🛠️$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)fix$(NC)           $(PURPLE)# Format and fix code style 🎨$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)py$(NC)            $(PURPLE)# Create new Python package template 🐍$(NC)\n\
	$(GREEN)make$(NC) $(YELLOW)rs$(NC)            $(PURPLE)# Create new Rust package template 🦀$(NC)\n\
	\n\
	$(CYAN)💡 Usage Examples:$(NC)\n\
	  $(GREEN)make$(NC) $(YELLOW)dev$(NC)         $(BLUE)# Setup development environment$(NC)\n\
	  $(GREEN)make$(NC) $(YELLOW)test$(NC)        $(BLUE)# Run all tests$(NC)\n\
	  $(GREEN)make$(NC) $(YELLOW)fix$(NC)         $(BLUE)# Format code$(NC)\n\
	  $(GREEN)make$(NC) $(YELLOW)py$(NC)          $(BLUE)# Create new Python package$(NC)\n"

.PHONY: dev bdist clean_dist publish test test_raw bins dirs all docs update init fix py rs help