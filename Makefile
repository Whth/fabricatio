DIST:=dist
DATA:=extra
PY:=3.13


all:bdist

dirs:
	mkdir -p $(DIST) $(DATA)


dev:
	cargo build --workspace --bins -r -Z unstable-options --artifact-dir $(DATA)/scripts
	rm $(DATA)/scripts/*.pdb |true
	rm $(DATA)/scripts/*.dwarf |true
	uvx -p $(PY) --project . maturin develop --uv -r

bdist: dirs clean dev
	uvx -p $(PY) --project . maturin build --sdist -r -o $(DIST)
	uv run publish_subpackages.py --no-publish

clean:
	rm -rf $(DIST)/* $(DATA)/*


test:dev
	uvx -p  $(PY) --project . pytest tests

publish:
	uv run publish_subpackages.py


.PHONY:  dev bdist clean publish test