"""Fabricatio Novel CLI entry point.

Simple typer app wrapping the novel composition chain:

- ``w``           — generate a novel from an outline
- ``wr``          — generate a novel with writing style RAG (lancedb)
- ``bible``       — create / update / show the setting bible
- ``store-refs``  — ingest text files as writing style references (lancedb)
- ``enrich-refs`` — chunk, enrich into QA pairs, and store references (lancedb)

The commands live in feature modules under :mod:`fabricatio_novel.commands`;
this module owns the ``typer`` apps and triggers their registration below.
"""

import typer

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")
bible_app = typer.Typer(help="Create, update, and show the setting bible (设定集).")
app.add_typer(bible_app, name="bible")

# Side-effect imports: each module registers its commands onto `app` at module
# load time. Must come AFTER `app` is defined.
from fabricatio_novel.commands import bible, references, writing  # noqa: F401

if __name__ == "__main__":
    app()
