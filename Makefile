DIST:=dist
DATA:=extra
PY:=3.12


all:bdist

tools:
	cargo build --all --bins -Z unstable-options --artifact-dir $(DATA)/scripts --release
	mkdir -p $(DATA)/scripts
	rm $(DATA)/scripts/*.pdb || true
	rm $(DATA)/scripts/*.dwarf || true

dev: tools
	uvx -p $(PY) --project . maturin develop --uv -r

bdist:clean tools
	uvx -p $(PY) --project . maturin sdist -o $(DIST)
	uvx -p $(PY) --project . maturin build  -r -o $(DIST)

clean:
	rm -rf $(DIST) $(DATA)

publish:tools
	uvx -p $(PY) --project . maturin publish --skip-existing
	uvx -p $(PY) --project . maturin upload --skip-existing $(DIST)/*
.PHONY: tools dev bdist clean publish