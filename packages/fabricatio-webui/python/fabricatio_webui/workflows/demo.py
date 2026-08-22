"""Workflows defined in fabricatio-webui."""

from fabricatio_core.models.action import WorkFlow

from fabricatio_webui.actions.demo import SummarizeStats, TextStats

#: Two-step demo pipeline: no LLM, no network, runs immediately.
#: Publish any task to the ``demo`` namespace with ``text`` in the extra
#: init context and this serves it offline.
HelloFabricatio = WorkFlow(
    name="Hello Fabricatio",
    description=(
        "Two-step pure-Python demo: count characters/words/lines of the "
        "input text, then format a summary line. Needs no LLM and no API "
        "keys — run it right away to see the board → role → task pipeline."
    ),
    steps=(TextStats(), SummarizeStats()),
)
