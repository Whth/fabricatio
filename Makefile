DIST:=dist
DATA:=extra
PY:=3.13


all:bdist

dirs:
	mkdir -p $(DIST) $(DATA)

bins: dirs
	uv run subpackages.py -py $(PY) --bins

dev: dirs
	uv run subpackages.py -py $(PY) --bins --dev

clean_dist:
	rm -rf $(DIST)/*

bdist: dirs clean_dist
	uv run subpackages.py -py $(PY) --bdist


test_raw:
	uv run pytest python/tests packages/*/python/tests --cov

test: dev
	uv sync --extra full
	make test_raw

publish:
	uv run subpackages.py -py $(PY) --publish

docs:
	make -C docs html
.PHONY:  dev bdist clean_dist publish test test_raw bins dirs all docs