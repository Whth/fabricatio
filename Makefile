DIST:=dist
DATA:=extra
PY:=3.13


all:bdist


dev:
	uvx -p $(PY) --project . maturin develop --uv -r

bdist:clean
	uvx -p $(PY) --project . maturin sdist -o $(DIST)
	uvx -p $(PY) --project . maturin build  -r -o $(DIST)

clean:
	rm -rf $(DIST) $(DATA)

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