"""LanceDB-backed storage CLI commands (lancedb-gated).

Registers onto the shared ``app`` from :mod:`fabricatio_novel.cli`:

- ``store-refs``   — :func:`store_reference_texts` (raw chunks)
- ``enrich-refs``  — :func:`store_enriched_texts` (LLM-enriched QA chunks)
"""

from typing import Optional

import typer
from fabricatio_core import Event, Role, Task
from fabricatio_core.decorators import cfg_on

from fabricatio_novel.cli import app
from fabricatio_novel.commands._helpers import _collect_files, _exit_on_error

_EMBED_NDIM: typer.Option = typer.Option(
    None,
    "--ndim",
    "-nd",
    help="Embedding vector dimensionality. Must match the embedding model's output dimension.",
    envvar="FABRICATIO_EMBEDDING__NDIM",
)
_EMBED_SEND_TO: typer.Option = typer.Option(
    None,
    "--send-to",
    "-st",
    help="Routing group for embedding requests.",
    envvar="FABRICATIO_EMBEDDING__SEND_TO",
)
_BATCH_SIZE: typer.Option = typer.Option(
    10, "--batch-size", "-bs", help="Number of chunks per storage batch.", envvar="NOVEL_BATCH_SIZE"
)
_PARALLEL_SIZE: typer.Option = typer.Option(
    10, "--parallel-size", "-ps", help="Number of worker sending embedding reqs.", envvar="NOVEL_PARALLEL_SIZE"
)


@app.command(name="store-refs")
@cfg_on(["lancedb"])
def store_reference_texts(
    patterns: list[str] = typer.Argument(
        ...,
        help="File paths and/or glob patterns to ingest (e.g. 'refs/*.txt').",
    ),
    chunks_size: int = typer.Option(
        512, "--chunks-size", "-cs", help="Maximum words per chunk when splitting files.", envvar="NOVEL_CHUNKS_SIZE"
    ),
    overlap: float = typer.Option(
        0.3, "--overlap", "-ov", help="Overlap ratio between consecutive chunks (0.0–1.0).", envvar="NOVEL_OVERLAP"
    ),
    ndim: Optional[int] = _EMBED_NDIM,
    embedding_send_to: Optional[str] = _EMBED_SEND_TO,
    batch_size: int = _BATCH_SIZE,
    parallel_size: int = _PARALLEL_SIZE,
) -> None:
    """Ingest text files as writing style references into the LanceDB vector store.

    Accepts literal file paths and glob patterns. All matching files are
    collected, deduplicated, and indexed. This is a standalone operation —
    it does not trigger novel generation.
    """
    from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig

    from fabricatio_novel.workflows.novel_rag import StoreWritingStyleTextsWorkflow

    store_refs_ns = "store_refs"
    Role.with_bio(name="ref_ingester").subscribe(
        Event.quick_instantiate(store_refs_ns), StoreWritingStyleTextsWorkflow
    ).dispatch()

    files = _collect_files(patterns)

    typer.echo(f"Ingesting {len(files)} file(s) as writing style references...")
    for f in files:
        typer.echo(f"  • {f}")

    conf = LancedbAddRAGConfig.default()
    conf.embedding_batch_size = batch_size
    conf.embedding_parallel_size = parallel_size
    task = Task(name="Store writing style references").update_init_context(
        text_files=files,
        chunk_size=chunks_size,
        chunk_overlap_ratio=overlap,
        store_config=conf,
        embedding_ndim=ndim,
        embedding_send_to=embedding_send_to,
    )

    result = task.delegate_blocking(store_refs_ns)

    if result is not None:
        typer.secho(
            f"✅ Successfully ingested {result} file(s) as writing style references.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        _exit_on_error("❌ Failed to store writing style reference texts.")


@app.command(name="enrich-refs")
@cfg_on(["lancedb"])
def store_enriched_texts(  # noqa: PLR0913
    patterns: list[str] = typer.Argument(
        ...,
        help="File paths and/or glob patterns to enrich and ingest (e.g. 'corpus/*.txt').",
    ),
    enrich_guideline: str = typer.Option(
        "",
        "--enrich-guideline",
        "-eg",
        help="Guidance passed to the LLM for QA-pair generation (e.g. 'Extract world-building facts').",
    ),
    chunk_guideline: str = typer.Option(
        "",
        "--chunk-guideline",
        "-cg",
        help="Guidance passed to the LLM for semantic splitting of source files (e.g. 'Split on scene boundaries').",
    ),
    chunk_max_size: int = typer.Option(5, "--chunk-max-size", "-cmx", help="Maximum mini-chunks per output chunk."),
    chunk_min_size: int = typer.Option(2, "--chunk-min-size", "-cmn", help="Minimum mini-chunks per output chunk."),
    mini_chunk_size: Optional[int] = typer.Option(
        None,
        "--mini-chunk-size",
        "-mcs",
        help="Mini-chunk character size (defaults to rag_config.mini_chunk_size).",
    ),
    ndim: Optional[int] = _EMBED_NDIM,
    embedding_send_to: Optional[str] = _EMBED_SEND_TO,
    batch_size: int = _BATCH_SIZE,
    parallel_size: int = _PARALLEL_SIZE,
) -> None:
    """Ingest text files as LLM-enriched QA chunks into the LanceDB vector store.

    Each input file is read, semantically split via `PreciseChunkText.precise_chunk`,
    fed chunk-by-chunk to `EnrichChunkTextNovel.enrich` to produce question-answer
    pairs, and each pair is indexed as a separate `EnrichedDocument`. This is a
    standalone operation — it does not trigger novel generation.
    """
    from fabricatio_novel.models.novel_enrich import EnrichedAddConfig
    from fabricatio_novel.workflows.novel_enrich import StoreEnrichedTextsWorkflow

    enrich_refs_ns = "enrich_refs"
    Role.with_bio(name="enriched_ref_ingester").subscribe(
        Event.quick_instantiate(enrich_refs_ns), StoreEnrichedTextsWorkflow
    ).dispatch()

    files = _collect_files(patterns)

    typer.echo(f"Enriching and ingesting {len(files)} file(s)...")
    for f in files:
        typer.echo(f"  • {f}")

    conf = EnrichedAddConfig.default()
    conf.embedding_batch_size = batch_size
    conf.embedding_parallel_size = parallel_size
    task = Task(name="Store LLM-enriched QA chunks").update_init_context(
        text_files=files,
        enrich_guideline=enrich_guideline,
        chunk_guideline=chunk_guideline,
        chunk_max_size=chunk_max_size,
        chunk_min_size=chunk_min_size,
        mini_chunk_size=mini_chunk_size,
        store_config=conf,
        embedding_ndim=ndim,
        embedding_send_to=embedding_send_to,
    )

    result = task.delegate_blocking(enrich_refs_ns)

    if result is not None:
        typer.secho(f"✅ Successfully stored {result} enriched QA chunk(s).", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to store enriched QA chunks.")
