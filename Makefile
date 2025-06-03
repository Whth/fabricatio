DIST:=dist
DATA:=extra
PY:=3.13


all:bdist

dirs:
	mkdir -p $(DIST) $(DATA)


bins: dirs
	cargo build -p fabricatio --bins -r -Z unstable-options --artifact-dir $(DATA)/scripts
	rm $(DATA)/scripts/*.pdb -f
	rm $(DATA)/scripts/*.dwarf -f

dev: dirs bins
	uvx -p $(PY) --project . maturin develop --uv -r
	uv run subpackages.py --no-publish --pyversion $(PY) --dev


bdist: dirs bins

	uvx -p $(PY) --project . maturin build --sdist -r -o $(DIST)
	uv run subpackages.py --no-publish --pyversion $(PY)

clean:
	rm -rf $(DIST)/* $(DATA)/*


test:dev
	uv sync --extra full
	uv run pytest python/tests packages/*/python/tests

publish: bdist
	uv run subpackages.py --pyversion $(PY)
	uvx -p $(PY) --project . maturin publish || true


docs:
	make -C docs html
.PHONY:  dev bdist clean publish tests bins dirs all docs