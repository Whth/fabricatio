"""A module containing some builtin workflows."""

__all__ = []

from fabricatio_core.rust import is_installed

if is_installed("fabricatio_typst") and is_installed("fabricatio_actions"):
    from fabricatio_typst.workflows.articles import WriteOutlineCorrectedWorkFlow

    __all__ += ["WriteOutlineCorrectedWorkFlow"]


if is_installed("fabricatio_actions") and is_installed("fabricatio_novel"):
    from fabricatio_novel.workflows.novel import (
        DebugNovelWorkflow,
        DumpOnlyWorkflow,
        GenerateOnlyCharactersWorkflow,
        RegenerateWithNewCharactersWorkflow,
        RewriteChaptersOnlyWorkflow,
        ValidatedNovelWorkflow,
        WriteNovelWorkflow,
    )

    __all__ += [
        "DebugNovelWorkflow",
        "DumpOnlyWorkflow",
        "GenerateOnlyCharactersWorkflow",
        "RegenerateWithNewCharactersWorkflow",
        "RewriteChaptersOnlyWorkflow",
        "ValidatedNovelWorkflow",
        "WriteNovelWorkflow",
    ]
