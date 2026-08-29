"""Tests for the execution-feedback mechanism (models.feedback + Handle loop)."""

from pathlib import Path
from typing import Unpack

from fabricatio_context.models.context import ContextLog
from fabricatio_core.models.kwargs_types import ChooseKwargs, ValidateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_tool.capabilities.handle import Handle
from fabricatio_tool.config import tool_config
from fabricatio_tool.models.collector import ApplicationError, ResultCollector
from fabricatio_tool.models.feedback import (
    FeedbackPayload,
    failure_entries,
    feedback_log,
    render_feedback,
    summarize_collector,
)
from fabricatio_tool.models.tool import Tool, ToolBox
from pydantic import Field, PrivateAttr


def boom() -> None:
    """A tool that always raises."""
    raise ValueError("boom")


class ScriptedHandle(Handle):
    """Handle double: scripts drafting rounds, records feedback."""

    drafts: list[dict[str, str | None]] = Field(default_factory=list)
    """The feedback observed by each drafting round."""

    _sources: list[str] = PrivateAttr(default_factory=list)

    def __init__(self, sources: list[str]) -> None:
        """Initialize with the scripted draft sources."""
        super().__init__()
        self._sources = list(sources)

    async def gather_tools_fine_grind(
        self,
        request: str,
        box_choose_kwargs: ChooseKwargs[ToolBox] | None = None,
        tool_choose_kwargs: ChooseKwargs[Tool] | None = None,
        send_to: str | None = None,
    ) -> list[Tool]:
        """Return the boom tool regardless of the request."""
        return [Tool(source=boom, name="boom", description="Always raises")]

    async def draft_tool_usage_code(
        self,
        request: str,
        tools: list[Tool],
        data: dict[str, str],
        output_spec: dict[str, str] | None = None,
        exec_feedback: str | None = None,
        send_to: str | None = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> str | None:
        """Record the feedback and return the next scripted source."""
        self.drafts.append({"exec_feedback": exec_feedback})
        return self._sources.pop(0) if self._sources else None


class TestSummarize:
    """Pure snapshot and render behavior."""

    def test_deterministic_and_key_sorted(self) -> None:
        """Snapshot and render must be byte-stable and key-sorted."""
        collector = ResultCollector().submit("z", {"b": 1, "a": [2, 1]}).submit("a", "x")
        first = summarize_collector(collector)
        second = summarize_collector(collector)
        assert list(first.results) == ["a", "z"]
        assert first == second
        assert render_feedback(first) == render_feedback(second)

    def test_error_key_excluded_and_carried(self) -> None:
        """The error entry must leave results and surface via error/source."""
        error = ApplicationError(exc_type="TypeError", message="boom", traceback="tb", source="src")
        collector = ResultCollector().submit("ok", 1).submit(tool_config.error_key, error)
        payload = summarize_collector(collector)
        assert "ok" in payload.results
        assert tool_config.error_key not in payload.results
        assert payload.error == "[TypeError] boom\n\nTraceback:\ntb"
        assert payload.source == "src"

    def test_repr_fallback_and_truncation(self) -> None:
        """Non-JSON values must fall back to repr and honor the char cap."""
        path_collector = ResultCollector().submit("path", Path("some/long/path/that/exceeds/the/cap"))
        truncated = summarize_collector(path_collector, max_chars=30)
        assert "truncated" in truncated.results["path"]
        object_collector = ResultCollector().submit("obj", object())
        repr_payload = summarize_collector(object_collector)
        assert "<object object at" in repr_payload.results["obj"]

    def test_empty_payload_renders_empty(self) -> None:
        """An empty payload must render to the empty string."""
        assert render_feedback(FeedbackPayload(results={}, error=None, source=None)) == ""


class TestTemplateTail:
    """Prefix-cache property of the draft template with feedback appended."""

    def test_feedback_is_strict_suffix(self) -> None:
        """The feedback render must only extend the prompt, never shift its prefix."""
        base_args: dict[str, object] = {
            "collector_help": ResultCollector.__doc__,
            "collector_varname": "collector",
            "fn_header": "async def execute(collector)->None:",
            "request": "Do the thing",
            "tools": [{"name": "boom", "briefing": "Always raises"}],
            "data": {"dir": "src/"},
            "output_spec": {"out": "the output"},
            "last_error": None,
        }
        no_feedback = TEMPLATE_MANAGER.render_template(tool_config.draft_tool_usage_code_template, base_args)
        feedback = '**Results collected during the failed execution:**\n- "partial": 42'
        with_feedback = TEMPLATE_MANAGER.render_template(
            tool_config.draft_tool_usage_code_template,
            {**base_args, "exec_feedback": feedback},
        )
        assert with_feedback.startswith(no_feedback)
        assert feedback in with_feedback

    def test_static_head_shared_across_requests(self) -> None:
        """Requests with different data must share the static head byte-for-byte."""
        base_args: dict[str, object] = {
            "collector_help": "help text",
            "collector_varname": "collector",
            "fn_header": "async def execute(collector)->None:",
            "request": "placeholder",
            "tools": [{"name": "boom", "briefing": "Always raises"}],
            "data": {},
            "output_spec": {},
            "last_error": None,
        }
        first = TEMPLATE_MANAGER.render_template(
            tool_config.draft_tool_usage_code_template,
            {**base_args, "request": "Count lines", "data": {"dir": "src/"}},
        )
        second = TEMPLATE_MANAGER.render_template(
            tool_config.draft_tool_usage_code_template,
            {**base_args, "request": "Rename files", "data": {"root": "docs/"}},
        )
        marker = "**Available Data:**"
        cut = first.index(marker)
        assert second.index(marker) == cut
        assert first[:cut] == second[:cut]
        assert "## Response Rules" in first[:cut]


class TestFeedbackLoop:
    """The Feedback capability retry loop."""

    async def test_retries_with_feedback_on_failure(self) -> None:
        """A failed round must feed results, error, and source into the next draft."""
        handle = ScriptedHandle(
            ['collector.submit("partial", 42)\nlen(None)\n', 'print("done")\n'],
        )
        collector = await handle.handle_fine_grind("Count something", {}, max_feedback_rounds=1)
        assert collector is not None
        assert collector.error() is None
        assert len(handle.drafts) == 2
        assert handle.drafts[0]["exec_feedback"] is None
        feedback = handle.drafts[1]["exec_feedback"]
        assert feedback is not None
        assert '"partial"' in feedback
        assert "TypeError" in feedback
        assert "len(None)" in feedback

    async def test_exhausted_rounds_keep_last_error(self) -> None:
        """After the final round, the collector must retain the last error."""
        handle = ScriptedHandle(
            ['collector.submit("partial", 1)\nlen(None)\n', 'collector.submit("partial", 2)\nlen(None)\n'],
        )
        collector = await handle.handle_fine_grind("Count something", {}, max_feedback_rounds=1)
        assert collector is not None
        assert collector.error() is not None
        assert len(handle.drafts) == 2
        feedback = handle.drafts[1]["exec_feedback"]
        assert feedback is not None
        assert "partial" in feedback

    async def test_rejection_feeds_back_code_and_exception(self) -> None:
        """A pre-execution check rejection must feed the run code and exception into the next draft."""
        handle = ScriptedHandle(
            ["import json\n", 'print("done")\n'],
        )
        collector = await handle.handle_fine_grind("Count something", {}, max_feedback_rounds=1)
        assert collector is not None
        assert collector.error() is None
        assert len(handle.drafts) == 2
        feedback = handle.drafts[1]["exec_feedback"]
        assert feedback is not None
        assert "Violations" in feedback
        assert "import json" in feedback
        assert "ValueError" in feedback

    async def test_all_failed_tries_accumulate_in_feedback(self) -> None:
        """Every failed try's error and source must stay visible in later drafts."""
        handle = ScriptedHandle(
            [
                'collector.submit("partial", 1)\nlen(None)\n',
                'collector.submit("partial", 2)\nint("abc")\n',
                'print("done")\n',
            ],
        )
        collector = await handle.handle_fine_grind("Count something", {}, max_feedback_rounds=2)
        assert collector is not None
        assert collector.error() is None
        assert len(handle.drafts) == 3
        first_feedback = handle.drafts[1]["exec_feedback"]
        second_feedback = handle.drafts[2]["exec_feedback"]
        assert first_feedback is not None
        assert second_feedback is not None
        assert "NoneType" in first_feedback
        assert "NoneType" in second_feedback  # first try still visible
        assert "invalid literal" in second_feedback  # second try's exception
        assert "invalid literal" not in first_feedback


class TestHistoryAccumulation:
    """Accumulated failure history rendering."""

    def test_feedback_log_with_history_keeps_every_failed_try(self) -> None:
        """feedback_log must render all historical failures plus one fresh results section."""
        first = FeedbackPayload(results={"partial": "42"}, error="E1", source="S1")
        second = FeedbackPayload(results={"extra": "1"}, error="E2", source="S2")
        history = ContextLog().with_entries(failure_entries(first)).with_entries(failure_entries(second))
        log = feedback_log(second, history=history)
        bodies = [entry.body for entry in log.entries]
        assert any("E1" in body for body in bodies)
        assert any("S1" in body for body in bodies)
        assert any("E2" in body for body in bodies)
        assert any("S2" in body for body in bodies)
        assert sum("Results collected" in body for body in bodies) == 1
