"""Fabricatio Novel CLI entry point.

Simple typer app wrapping the novel composition chain:

- ``w``           — generate a novel from an outline
- ``wr``          — generate a novel with writing style RAG (lancedb)
- ``store-refs``  — ingest text files as writing style references (lancedb)
- ``enrich-refs`` — chunk, enrich into QA pairs, and store references (lancedb)
"""

import asyncio
from pathlib import Path
from typing import List, Optional

import typer
from fabricatio_core import Role

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")


class WriterRole(Role, NovelCompose):
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
    language: str | None = None,
    output: Optional[Path] = None,
    font: Optional[Path] = None,
    cover: Optional[Path] = None,
) -> Path:
    persist_dir.mkdir(parents=True, exist_ok=True)
    novel.persist(persist_dir)
    epub_path = persist_dir / output if output else persist_dir / "novel.epub"
    novel.dump_epub(epub_path, language=language, font=font, cover=cover)
    typer.secho(
        f"✅ Novel '{novel.title}' generated with {len(novel.chapter)} chapter(s)\n"
        f"   JSON:  {persist_dir}\n"
        f"   EPUB:  {epub_path}",
        fg=typer.colors.GREEN,
        bold=True,
    )
    return epub_path


@app.command(name="w")
def write_novel(
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
) -> None:
    """Generate a novel from an outline."""
    ctx = NovelContext.create(_resolve_outline(outline, outline_file), language)
    role = WriterRole(name="writer")
    novel = _compose(ctx, role, send_to)
    if novel is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _persist(novel, persist_dir, ctx.language, output=output, font=font, cover=cover)


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
        0, "--retrieve-limit", "-rl", help="Reference documents retrieved per refined query (0 = default 15)."
    ),
    font: Optional[Path] = typer.Option(
        None, "--font", "-f", help="Font file (.ttf) to embed in the EPUB and apply to its body text."
    ),
    cover: Optional[Path] = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="EPUB output file name (relative to --persist-dir)."
    ),
) -> None:
    """Generate a novel with writing style RAG from an outline."""
    from fabricatio_novel.capabilities.rag import RAGCompose

    class WriterRAGRole(Role, NovelCompose, RAGCompose):
        """Writer role with writing style retrieval."""

    ctx = NovelContext.create(_resolve_outline(outline, outline_file), language)
    role = WriterRAGRole(name="writer", rag_query=rag_query or "", rag_limit=retrieve_limit)
    novel = _compose(ctx, role, send_to)
    if novel is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _persist(novel, persist_dir, ctx.language, output=output, font=font, cover=cover)


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
