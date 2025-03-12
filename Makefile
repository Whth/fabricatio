DIST:=dist
DATA:=extra



all:bdist

tools:
	cargo build --all --bins -Z unstable-options --artifact-dir $(DATA)/scripts --release
	mkdir -p $(DATA)/scripts
	rm $(DATA)/scripts/*.pdb || true
	rm $(DATA)/scripts/*.dwarf || true

dev: tools
	uvx --project . maturin develop --uv -r

bdist:clean tools
	uvx --project . maturin sdist -o $(DIST)
	uvx --project . maturin build  -r -o $(DIST)

clean:
	rm -rf $(DIST) $(DATA)

publish:tools
	uvx --project . maturin publish --skip-existing
	uvx --project . maturin upload --skip-existing $(DIST)/*
.PHONY: tools