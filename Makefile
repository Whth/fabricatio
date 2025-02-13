DIST:=dist
DATA:=extra



all:bdist

tools:
	cargo build --all --bins -Z unstable-options --artifact-dir $(DATA)/scripts --release
	mkdir -p $(DATA)/scripts
	rm $(DATA)/scripts/*.pdb || true
	rm $(DATA)/scripts/*.dwarf || true

bdist:clean tools
	maturin sdist -o $(DIST)
	maturin build  -r -o $(DIST)

clean:
	rm -rf $(DIST) $(DATA)

.PHONY: tools