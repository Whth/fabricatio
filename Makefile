DIST:=dist
DATA:=extra
PY:=3.13


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
	ruff format
	ruff check --fix --unsafe-fixes
	cargo fmt

.PHONY:  dev bdist clean_dist publish test test_raw bins dirs all docs update init fix