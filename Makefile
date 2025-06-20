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
	uv sync --extra full --group docs -U && cargo update --recursive --verbose
.PHONY:  dev bdist clean_dist publish test test_raw bins dirs all docs update