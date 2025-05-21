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

clean:
	rm -rf $(DIST)/* $(DATA)/*


publish:
	uvx -p $(PY) --project . maturin publish --skip-existing
	uvx -p $(PY) --project . maturin upload --skip-existing $(DIST)/*

test:dev
	uvx -p  $(PY) --project . pytest tests

packages:
	uv run publish_subpackages.py

publish_packages: packages
	uv publish dist/*


.PHONY:  dev bdist clean publish test publish_packages packages