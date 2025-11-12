"""This module defines various workflows for novel generation, from full pipelines to granular steps.

Each workflow is designed for specific use cases: full generation, debugging, component regeneration, validation, etc.
"""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from pathlib import Path

from fabricatio_actions.actions.output import PersistentAll
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateChaptersFromScripts,
    GenerateCharactersFromDraft,
    GenerateNovel,  # One-step full pipeline
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)

# ==============================
# 🚀 One-Step Full Novel Generation (Existing, standardized)
# ==============================
WriteNovelWorkflow = WorkFlow(
    name="WriteNovelWorkflow",
    description="Generate and dump a novel from outline in one go.",
    steps=(GenerateNovel, DumpNovel().to_task_output(), PersistentAll),
)
"""Generate a novel from outline and dump it to file."""

# ==============================
# 🧩 Step-by-Step Debug Workflow (Recommended for development)
# ==============================
DebugNovelWorkflow = WorkFlow(
    name="DebugNovelWorkflow",
    description="Step-by-step novel generation for inspection and debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScripts,
        PersistentAll,
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use this workflow to debug each stage of novel generation."""


# ==============================
# 🎭 Generate Characters Only (For character design phase)
# ==============================
GenerateOnlyCharactersWorkflow = WorkFlow(
    name="GenerateOnlyCharactersWorkflow",
    description="Generate character cards from a given novel draft.",
    steps=(
        GenerateNovelDraft,
        GenerateCharactersFromDraft,
        PersistentAll,
    ),
)
"""Useful for iterating on character design before full generation."""


# ==============================
# 📖 Rewrite Chapters Only (Reuse scripts + characters → regenerate prose)
# ==============================
RewriteChaptersOnlyWorkflow = WorkFlow(
    name="RewriteChaptersOnlyWorkflow",
    description="Regenerate chapter contents from existing scripts and characters.",
    steps=(
        GenerateChaptersFromScripts,  # expects draft, scripts, characters in context
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use when you want to rewrite chapter prose without changing plot or characters."""


# ==============================
# ✅ Validated Full Pipeline (Production-grade with quality checks)
# ==============================
ValidatedNovelWorkflow = WorkFlow(
    name="ValidatedNovelWorkflow",
    description="Generate novel with post-generation validation for quality control.",
    steps=(
        GenerateNovel,
        ValidateNovel,  # Halts or warns if validation fails (depends on engine)
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Ideal for production: ensures minimum chapters, word count, and compliance ratio."""


# ==============================
# 🔄 Regenerate with New Characters (A/B test character impact)
# ==============================
RegenerateWithNewCharactersWorkflow = WorkFlow(
    name="RegenerateWithNewCharactersWorkflow",
    description="Reuse existing draft but regenerate story with new characters.",
    steps=(
        GenerateNovelDraft,  # Or inject pre-existing draft via context
        GenerateCharactersFromDraft,  # May yield different characters
        GenerateScriptsFromDraftAndCharacters,
        GenerateChaptersFromScripts,
        AssembleNovelFromComponents,
        DumpNovel(output_path=Path("output_with_new_characters.epub")).to_task_output(),
        PersistentAll,
    ),
)
"""Use to explore how different character sets affect narrative outcomes."""


# ==============================
# 💾 Dump Only Workflow (For pre-generated Novel objects)
# ==============================
DumpOnlyWorkflow = WorkFlow(
    name="DumpOnlyWorkflow",
    description="Only dump an existing Novel object to file (no generation).",
    steps=(
        DumpNovel,
        PersistentAll,
    ),
)
"""Use when Novel is pre-generated or loaded from DB/cache."""
