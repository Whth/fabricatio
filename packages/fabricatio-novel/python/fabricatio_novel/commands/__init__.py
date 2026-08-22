"""Command modules for the Fabricatio Novel CLI.

Each submodule registers its commands onto the ``typer`` apps owned by
``fabricatio_novel.cli`` at import time. Import submodules by name — never
re-export them here, so importing a single helper does not load every command.
"""
