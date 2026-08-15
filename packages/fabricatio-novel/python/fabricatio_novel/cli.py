"""Fabricatio Novel CLI entry point.

Simple typer app wrapping the novel composition chain:

- ``w``           — generate a novel from an outline
- ``wr``          — generate a novel with writing style RAG (lancedb)
- ``bible``       — create / update / show the setting bible
- ``store-refs``  — ingest text files as writing style references (lancedb)
- ``enrich-refs`` — chunk, enrich into QA pairs, and store references (lancedb)
"""

import asyncio
from pathlib import Path
from typing import List, Optional

import typer
from fabricatio_core import TEMPLATE_MANAGER, Role

from fabricatio_novel.capabilities.bible import BibleCompose
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.series_book import SeriesBible

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")
bible_app = typer.Typer(help="Create, update, and show the setting bible (设定集).")
app.add_typer(bible_app, name="bible")


class WriterRole(Role, NovelCompose, BibleCompose):
    """Writer role for base novel generation."""


def _collect_files(patterns: List[str]) -> List[Path]:
    files = set()
    for pattern in patterns:
        p = Path(pattern)
        if not any(ch in pattern for ch in "*?["):
            if p.is_file():
                files.add(p.resolve())
            continue
        root = Path(p.root or ".")
        rel = pattern[len(p.root) :] if p.root else pattern
        for match in root.glob(rel):
            if match.is_file():
                files.add(match.resolve())
    return sorted(files)


def _resolve_outline(outline: Optional[str], outline_file: Optional[Path]) -> str:
    if outline_file is not None:
        text = outline_file.read_text(encoding="utf-8").strip()
        if not text:
            typer.secho(f"❌ Outline file '{outline_file}' is empty.", fg=typer.colors.RED, bold=True)
            raise typer.Exit(1)
        return text
    if outline:
        return outline
    typer.secho(
        "❌ Provide the outline as a positional argument or via --outline-file.", fg=typer.colors.RED, bold=True
    )
    raise typer.Exit(1)


def _compose(ctx: NovelContext, role: NovelCompose, send_to: str) -> Optional[Novel]:
    return asyncio.run(role.compose_novel(ctx, send_to=send_to))


def _persist(
    novel: Novel,
    persist_dir: Path,
    output: Optional[Path] = None,
    font: Optional[Path] = None,
    cover: Optional[Path] = None,
) -> Path:
    persist_dir.mkdir(parents=True, exist_ok=True)
    novel.persist(persist_dir)
    epub_path = persist_dir / output if output else persist_dir / "novel.epub"
    novel.dump_epub(epub_path, font=font, cover=cover)
    typer.secho(
        f"✅ Novel '{novel.title}' generated with {len(novel.chapter)} chapter(s)\n"
        f"   JSON:  {persist_dir}\n"
        f"   EPUB:  {epub_path}",
        fg=typer.colors.GREEN,
        bold=True,
    )
    return epub_path


def _load_bible(path: Path) -> SeriesBible:
    """Load a SeriesBible from its JSON file."""
    if not path.is_file():
        typer.secho(f"❌ Bible file '{path}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    return SeriesBible.model_validate_json(path.read_text(encoding="utf-8"))


def _render_bible_md(bible: SeriesBible) -> str:
    """Render the bible as a human-readable markdown document."""
    return TEMPLATE_MANAGER.render_template(novel_config.setting_bible_export_template, bible.model_dump())


def _save_bible(bible: SeriesBible, out: Path) -> None:
    """Write the bible JSON, a BLAKE3-hashed checkpoint, and the markdown export."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bible.model_dump_json(indent=1, by_alias=True), encoding="utf-8")
    bible.persist(out.parent)
    md_path = out.with_name(f"{out.stem}.md")
    md_path.write_text(_render_bible_md(bible), encoding="utf-8")
    typer.secho(
        f"✅ Setting bible saved:\n   JSON:       {out}\n   Markdown:   {md_path}\n   Checkpoint: {out.parent}",
        fg=typer.colors.GREEN,
        bold=True,
    )


@bible_app.command(name="create")
def create_bible(
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Bible language. Auto-detected from the outline when omitted."
    ),
    sections: str = typer.Option(
        "", "--sections", "-s", help="Comma-separated sections to create: characters, background (default: all)."
    ),
    out: Path = typer.Option(
        Path("settings/bible.json"), "--out", "-o", help="Output bible JSON path (default: settings/bible.json)."
    ),
    send_to: str = typer.Option("fla", "--send-to", "-st", help="Routing group for LLM calls."),
) -> None:
    """Create a setting bible from an outline."""
    from fabricatio_novel.capabilities.bible import parse_sections

    class BibleRole(Role, BibleCompose):
        """Role for creating and updating setting bibles."""

    try:
        names = parse_sections(sections)
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1) from None
    role = BibleRole(name="bible_creator")
    bible = asyncio.run(role.create_setting_bible(_resolve_outline(outline, outline_file), language, send_to, names))
    if bible is None:
        typer.secho("❌ Failed to create setting bible.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _save_bible(bible, out)


@bible_app.command(name="update")
def update_bible(
    bible_path: Path = typer.Argument(..., help="Path to the bible JSON to update."),
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Bible language. Auto-detected from the outline when omitted."
    ),
    sections: str = typer.Option(
        "", "--sections", "-s", help="Comma-separated sections to re-propose: characters, background (default: all)."
    ),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output bible JSON path (default: update in place)."),
    send_to: str = typer.Option("fla", "--send-to", "-st", help="Routing group for LLM calls."),
) -> None:
    """Re-propose sections of an existing setting bible from the outline."""
    from fabricatio_novel.capabilities.bible import parse_sections

    class BibleRole(Role, BibleCompose):
        """Role for creating and updating setting bibles."""

    bible = _load_bible(bible_path)
    try:
        names = parse_sections(sections)
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1) from None
    role = BibleRole(name="bible_updater")
    updated = asyncio.run(
        role.update_setting_bible(bible, _resolve_outline(outline, outline_file), language, send_to, names)
    )
    if updated is None:
        typer.secho("❌ Failed to update setting bible.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _save_bible(updated, out or bible_path)


@bible_app.command(name="show")
def show_bible(
    bible_path: Path = typer.Argument(..., help="Path to the bible JSON to display."),
) -> None:
    """Print the setting bible as rendered markdown."""
    typer.echo(_render_bible_md(_load_bible(bible_path)))


@app.command(name="w")
def write_novel(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Written language. Auto-detected from the outline when omitted."
    ),
    persist_dir: Path = typer.Option(
        Path("novels"), "--persist-dir", "-p", help="Directory to persist the generated novel JSON and EPUB."
    ),
    send_to: str = typer.Option("fla", "--send-to", "-st", help="Routing group for LLM calls."),
    font: Optional[Path] = typer.Option(
        None, "--font", "-f", help="Font file (.ttf) to embed in the EPUB and apply to its body text."
    ),
    cover: Optional[Path] = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="EPUB output file name (relative to --persist-dir)."
    ),
    bible: Optional[Path] = typer.Option(
        None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."
    ),
    constraint: Optional[str] = typer.Option(
        None,
        "--constraint",
        "-c",
        help="Global writing constraint to honor throughout the novel (e.g. 'first person view').",
    ),
) -> None:
    """Generate a novel from an outline."""
    ctx = NovelContext.create(_resolve_outline(outline, outline_file), language)
    ctx.set_writing_constraint(constraint or "")
    if bible is not None:
        ctx.set_series_bible(_load_bible(bible))
    role = WriterRole(name="writer")
    novel = _compose(ctx, role, send_to)
    if novel is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _persist(novel, persist_dir, output=output, font=font, cover=cover)


@app.command(name="wr")
def write_novel_with_rag(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Written language. Auto-detected from the outline when omitted."
    ),
    persist_dir: Path = typer.Option(
        Path("novels"), "--persist-dir", "-p", help="Directory to persist the generated novel JSON and EPUB."
    ),
    send_to: str = typer.Option("fla", "--send-to", "-st", help="Routing group for LLM calls."),
    rag_query: Optional[str] = typer.Option(
        None,
        "--rag-query",
        "-rq",
        help="Custom query guideline for writing style retrieval; defaults to per-scene descriptions.",
    ),
    retrieve_limit: int = typer.Option(
        0, "--retrieve-limit", "-rl", help="Final reference documents kept after reranking (0 = default 15)."
    ),
    font: Optional[Path] = typer.Option(
        None, "--font", "-f", help="Font file (.ttf) to embed in the EPUB and apply to its body text."
    ),
    cover: Optional[Path] = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="EPUB output file name (relative to --persist-dir)."
    ),
    bible: Optional[Path] = typer.Option(
        None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."
    ),
    constraint: Optional[str] = typer.Option(
        None,
        "--constraint",
        "-c",
        help="Global writing constraint to honor throughout the novel (e.g. 'first person view').",
    ),
) -> None:
    """Generate a novel with writing style RAG from an outline."""
    from fabricatio_novel.capabilities.rag import RAGCompose

    class WriterRAGRole(Role, NovelCompose, RAGCompose, BibleCompose):
        """Writer role with writing style retrieval."""

    ctx = NovelContext.create(_resolve_outline(outline, outline_file), language)
    ctx.set_writing_constraint(constraint or "")
    if bible is not None:
        ctx.set_series_bible(_load_bible(bible))
    ctx.set_rag_query(rag_query or "").set_rag_limit(retrieve_limit)
    role = WriterRAGRole(name="writer")
    novel = _compose(ctx, role, send_to)
    if novel is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _persist(novel, persist_dir, output=output, font=font, cover=cover)


@app.command(name="store-refs")
def store_reference_texts(
    patterns: List[str] = typer.Argument(..., help="File paths and/or glob patterns to ingest."),
    chunk_guideline: str = typer.Option("", "--chunk-guideline", "-cg", help="Guidance for semantic chunking."),
    max_size: int = typer.Option(5, "--max-size", "-ms", help="Maximum chunks per split."),
    min_size: int = typer.Option(2, "--min-size", "-mi", help="Minimum chunks per split."),
) -> None:
    """Ingest text files as writing style references into LanceDB."""
    from fabricatio_core.utils import cfg

    cfg(["lancedb"])
    from fabricatio_rag.capabilities.chunk import PreciseChunkText

    from fabricatio_novel.capabilities.rag import RAGCompose
    from fabricatio_novel.models.rag import WritingStyleAddConfig, WritingStyleDocument

    class IngestRole(Role, PreciseChunkText, RAGCompose):
        """Role for chunking and storing writing style references."""

    files = _collect_files(patterns)
    if not files:
        typer.secho("❌ No files matched the given patterns.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    typer.echo(f"Ingesting {len(files)} file(s) as writing style references...")
    role = IngestRole(name="ref_ingester")
    total = 0
    for path in files:
        chunks = asyncio.run(role.precise_chunk(chunk_guideline, path.read_text(encoding="utf-8"), max_size, min_size))
        if not chunks:
            continue
        docs = [WritingStyleDocument.with_text_chunk(c) for c in chunks]
        asyncio.run(role.add_document(docs, WritingStyleAddConfig.default()))
        total += len(docs)
        typer.echo(f"  • {path.name}: {len(docs)} chunk(s)")
    typer.secho(f"✅ Stored {total} writing style chunk(s).", fg=typer.colors.GREEN, bold=True)


@app.command(name="enrich-refs")
def store_enriched_texts(
    patterns: List[str] = typer.Argument(..., help="File paths and/or glob patterns to enrich and ingest."),
    enrich_guideline: str = typer.Option(
        "", "--enrich-guideline", "-eg", help="Guidance for QA-pair generation (e.g. 'Extract world-building facts')."
    ),
    chunk_guideline: str = typer.Option("", "--chunk-guideline", "-cg", help="Guidance for semantic chunking."),
    max_size: int = typer.Option(5, "--max-size", "-ms", help="Maximum chunks per split."),
    min_size: int = typer.Option(2, "--min-size", "-mi", help="Minimum chunks per split."),
) -> None:
    """Chunk reference texts, enrich them into QA pairs, and store in LanceDB."""
    from fabricatio_core.utils import cfg

    cfg(["lancedb"])
    from fabricatio_rag.capabilities.chunk import PreciseChunkText
    from fabricatio_rag.capabilities.enrich import EnrichChunkText

    from fabricatio_novel.capabilities.rag import RAGCompose
    from fabricatio_novel.models.rag import EnrichedAddConfig, EnrichedDocument

    class EnrichRole(Role, PreciseChunkText, EnrichChunkText, RAGCompose):
        """Role for chunking, enriching, and storing reference chunks."""

    files = _collect_files(patterns)
    if not files:
        typer.secho("❌ No files matched the given patterns.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    typer.echo(f"Enriching {len(files)} file(s) into QA pairs...")
    role = EnrichRole(name="ref_enricher")
    total = 0
    for path in files:
        chunks = asyncio.run(role.precise_chunk(chunk_guideline, path.read_text(encoding="utf-8"), max_size, min_size))
        if not chunks:
            continue
        results = asyncio.run(role.enrich(enrich_guideline, chunks))
        docs = [
            EnrichedDocument.with_text_chunk("\n".join(f"Q: {qa.question}\nA: {qa.answer}" for qa in result.qa_pairs))
            for result in results
        ]
        asyncio.run(role.add_document(docs, EnrichedAddConfig.default()))
        total += len(docs)
        typer.echo(f"  • {path.name}: {len(docs)} enriched chunk(s)")
    typer.secho(f"✅ Stored {total} enriched chunk(s).", fg=typer.colors.GREEN, bold=True)


if __name__ == "__main__":
    app()
