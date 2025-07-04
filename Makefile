DIST:=dist
DATA:=extra
PY:=3.13

PY_TEMPLATE_URL:=https://github.com/Whth/fabricatio-purepython-template

RS_TEMPLATE_URL:=https://github.com/Whth/fabricatio-maturin-template

PACKAGES:=packages


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

.PHONY:  dev bdist clean_dist publish test test_raw bins dirs all docs update init fix py rs