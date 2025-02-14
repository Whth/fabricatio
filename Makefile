DIST:=dist
DATA:=extra



all:bdist

tools:
	cargo build --all --bins -Z unstable-options --artifact-dir $(DATA)/scripts --release
	mkdir -p $(DATA)/scripts
	rm $(DATA)/scripts/*.pdb || true
	rm $(DATA)/scripts/*.dwarf || true

dev:
	uvx  --with-editable . maturin develop --uv -r

bdist:clean tools
	uvx  --with-editable . maturin sdist -o $(DIST)
	uvx  --with-editable . maturin build  -r -o $(DIST)

clean:
	rm -rf $(DIST) $(DATA)

publish:tools
	uvx  --with-editable . maturin publish --skip-existing
.PHONY: tools