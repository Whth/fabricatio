"""Mental state-enhanced novel generation workflows.

Includes combinations with RAG writing styles and ComfyUI illustration.
"""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_actions.actions.output import PersistentAll  # noqa: I001
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.illustration import IllustrateNovel
from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateCharactersFromDraft,
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)
from fabricatio_novel.actions.novel_mental import (
    GenerateChaptersFromScriptsWithMental,
    GenerateChaptersFromScriptsWithMentalRAG,
    GenerateNovelMental,
    GenerateNovelMentalRAG,
)


# ==============================
# 🧠 Mental State Full Novel Generation
# ==============================
WriteNovelWithMentalWorkflow = WorkFlow(
    name="WriteNovelWithMentalWorkflow",
    description="Generate and dump a novel with mental state tracking.",
    steps=(
        GenerateNovelMental,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Generate a novel from outline with mental state tracking and dump to file."""


# ==============================
# 🧩 Mental Debug Workflow (Step-by-step with persistence)
# ==============================
DebugNovelWithMentalWorkflow = WorkFlow(
    name="DebugNovelWithMentalWorkflow",
    description="Step-by-step novel generation with mental states for inspection and debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithMental,
        PersistentAll,
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use this workflow to debug each stage of mental-state novel generation."""


# ==============================
# ✅ Mental Validated Pipeline (Production-grade)
# ==============================
ValidatedNovelWithMentalWorkflow = WorkFlow(
    name="ValidatedNovelWithMentalWorkflow",
    description="Generate novel with mental states and post-generation validation.",
    steps=(
        GenerateNovelMental,
        ValidateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Production-grade novel generation with mental states and quality validation."""


# ==============================
# 🧠✍️ RAG + Mental Pipelines
# ==============================
WriteNovelWithMentalRAGWorkflow = WorkFlow(
    name="WriteNovelWithMentalRAGWorkflow",
    description="Generate and dump a novel with RAG writing styles + mental state tracking.",
    steps=(
        GenerateNovelMentalRAG,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Generate a novel with RAG writing style injection + mental state tracking."""


DebugNovelWithMentalRAGWorkflow = WorkFlow(
    name="DebugNovelWithMentalRAGWorkflow",
    description="Step-by-step novel generation with RAG + mental states for debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithMentalRAG,
        PersistentAll,
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Debug each stage of RAG + mental-state novel generation."""


ValidatedNovelWithMentalRAGWorkflow = WorkFlow(
    name="ValidatedNovelWithMentalRAGWorkflow",
    description="Generate novel with RAG + mental states and post-generation validation.",
    steps=(
        GenerateNovelMentalRAG,
        ValidateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Production-grade novel generation with RAG + mental states and quality validation."""


# ==============================
# 🧠🎨 Mental + Illustrated Pipelines
# ==============================
DebugMentalIllustratedNovelWorkflow = WorkFlow(
    name="DebugMentalIllustratedNovelWorkflow",
    description="Step-by-step mental-state novel generation with illustration for debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithMental,
        PersistentAll,
        AssembleNovelFromComponents,
        PersistentAll,
        IllustrateNovel,
        PersistentAll,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Debug each stage of mental-state + illustrated pipeline."""


# ==============================
# 🧠✍️🎨 RAG + Mental + Illustrated Pipelines
# ==============================
DebugMentalRAGIllustratedNovelWorkflow = WorkFlow(
    name="DebugMentalRAGIllustratedNovelWorkflow",
    description="Step-by-step RAG + mental-state novel generation with illustration for debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithMentalRAG,
        PersistentAll,
        AssembleNovelFromComponents,
        PersistentAll,
        IllustrateNovel,
        PersistentAll,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Debug each stage of RAG + mental-state + illustrated pipeline."""
