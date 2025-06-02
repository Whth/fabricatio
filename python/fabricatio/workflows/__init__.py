"""A module containing some builtin workflows."""

__all__ = []

from importlib.util import find_spec

if find_spec("fabricatio_typst") and find_spec("fabricatio_actions"):
    from fabricatio_typst.workflows.articles import WriteOutlineCorrectedWorkFlow

    __all__ += ["WriteOutlineCorrectedWorkFlow"]
