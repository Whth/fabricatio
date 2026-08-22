"""Reference-corpus commands: store and enrich writing style references in LanceDB."""

import asyncio
from pathlib import Path
from typing import List

import typer
from fabricatio_core import Role

from fabricatio_novel.cli import app


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
