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

clean_dev:
	rm -f ./python/*/*.pyd
	rm -f ./python/*/*.so
	rm -f ./packages/*/python/*/*.pyd
	rm -f ./packages/*/python/*/*.so

clean_dist:
	rm -rf $(DIST)/*

bdist: dirs clean_dev clean_dist bins
	uv build -p $(PY) -o dist --sdist --wheel --all-packages

test_raw:
	uv run pytest python/tests packages/*/python/tests --cov

test: dev
	uv sync --extra full
	make test_raw

publish: bdist
	uv run -p $(PY) subpackages.py  --publish

docs:
	make -C docs html
.PHONY:  dev bdist clean_dist clean_dev publish test test_raw bins dirs all docs