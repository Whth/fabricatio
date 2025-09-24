"""A module containing some builtin workflows."""

__all__ = []

from importlib.util import find_spec

if find_spec("fabricatio_typst") and find_spec("fabricatio_actions"):
    from fabricatio_typst.workflows.articles import WriteOutlineCorrectedWorkFlow

    __all__ += ["WriteOutlineCorrectedWorkFlow"]


if find_spec("fabricatio_actions") and find_spec("fabricatio_novel"):
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
