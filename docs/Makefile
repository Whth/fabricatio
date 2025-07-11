# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SPHINXINTL    ?= sphinx-intl
LANG             ?= zh_CN
SOURCEDIR     = source
BUILDDIR      = build

GETTEXTDIR       = $(BUILDDIR)/gettext

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

clean_text:
	@rm -rf $(GETTEXTDIR)

gettext: clean_text
	@$(SPHINXBUILD) -b gettext "$(SOURCEDIR)" "$(GETTEXTDIR)" $(SPHINXOPTS) $(O)
	@rm -rf $(GETTEXTDIR)/autoapi

intl: gettext intl_raw

intl_raw:
	@echo "Updating $(O)"
	@$(SPHINXINTL) update -p "$(GETTEXTDIR)" -l $(LANG) -j 1 # sphinx-intl seems get file exist error when run in parallel

.PHONY: help Makefile gettext intl intl_raw

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
