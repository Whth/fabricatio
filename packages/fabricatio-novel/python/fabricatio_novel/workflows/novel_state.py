"""Character state consistency-enhanced novel generation workflows."""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_actions.actions.output import PersistentAll  # noqa: I001
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateCharactersFromDraft,
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)
from fabricatio_novel.actions.novel_state import (
    GenerateChaptersFromScriptsWithState,
    GenerateNovelState,
)


# ==============================
# 🎯 State Consistency Full Novel Generation
# ==============================
WriteNovelWithStateWorkflow = WorkFlow(
    name="WriteNovelWithStateWorkflow",
    description="Generate and dump a novel with character state consistency tracking.",
    steps=(
        GenerateNovelState,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Generate a novel from outline with character state consistency and dump to file."""


# ==============================
# 🧩 State Consistency Debug Workflow (Step-by-step with persistence)
# ==============================
DebugNovelWithStateWorkflow = WorkFlow(
    name="DebugNovelWithStateWorkflow",
    description="Step-by-step novel generation with character state consistency for inspection and debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithState,
        PersistentAll,
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use this workflow to debug each stage of state-consistent novel generation."""


# ==============================
# ✅ State Consistency Validated Pipeline (Production-grade)
# ==============================
ValidatedNovelWithStateWorkflow = WorkFlow(
    name="ValidatedNovelWithStateWorkflow",
    description="Generate novel with character state consistency and post-generation validation.",
    steps=(
        GenerateNovelState,
        ValidateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Production-grade novel generation with character state consistency and quality validation."""
