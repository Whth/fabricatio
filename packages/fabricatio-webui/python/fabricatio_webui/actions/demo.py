"""Pure-Python demo actions for the webui.

These actions need **no LLM, no network, and no configuration** — they exist
so the "Hello Fabricatio" blueprint can be executed immediately after a fresh
install, demonstrating the board → role → task pipeline end to end.
"""

from fabricatio_core.models.action import Action


class TextStats(Action):
    """Count characters, words, and lines of the incoming text."""

    output_key: str = "stats"

    async def _execute(self, text: str = "", **cxt) -> dict[str, int]:
        return {
            "chars": len(text),
            "words": len(text.split()),
            "lines": text.count("\n") + 1 if text else 0,
        }


class SummarizeStats(Action):
    """Format a stats dictionary into a one-line human-readable summary."""

    output_key: str = "task_output"

    async def _execute(self, stats: dict[str, int], **cxt) -> str:
        parts = ", ".join(f"{key}: {value}" for key, value in stats.items())
        return f"[demo] {parts}"
