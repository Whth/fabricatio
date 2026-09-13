"""Tests for MockScript: ordered responses, strict exhaustion, reset-on-exit."""

from uuid import uuid4

import orjson
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import Value
from fabricatio_mock.models.mock_script import MockScript, ScriptExhaustedError


def _question(label: str) -> str:
    """Build a cache-unique question so scripted calls always reach the dummy queue.

    The router caches completions by prompt hash in a store shared with
    production runs, so every scripted call needs a fresh prompt.

    Args:
        label: Test-specific prefix.

    Returns:
        str: The question string.
    """
    return f"mock-script-{label}-{uuid4().hex}"


class TestMockScriptOrdering:
    """Responses are consumed in declaration order."""

    async def test_texts_return_in_order(self) -> None:
        """Two declared texts answer two successive calls, in order."""
        role = LLMTestRole(name="script-order")
        with MockScript.from_texts("first", "second"):
            first = await role.aask(question=_question("a"))
            second = await role.aask(question=_question("b"))

        assert first == "first"
        assert second == "second"

    async def test_json_value_is_parsed_by_caller(self) -> None:
        """A JSON value response carries the serialized payload."""
        role = LLMTestRole(name="script-json")
        with MockScript.from_values(Value.from_json({"tag": "rust"}, name="tags")):
            answer = await role.aask(question=_question("json"))

        assert orjson.loads(answer) == {"tag": "rust"}

    async def test_chained_values_keep_declaration_order(self) -> None:
        """with_text and with_values append after the existing declarations."""
        role = LLMTestRole(name="script-chain")
        script = MockScript.from_texts("first").with_text("second").with_values(Value.from_text("third", name="last"))
        assert [value.name for value in script.values] == ["text-1", "text-2", "last"]

        with script:
            answers = [await role.aask(question=_question(f"chain-{position}")) for position in range(3)]

        assert answers == ["first", "second", "third"]


class TestMockScriptStrictness:
    """Strict scripts fail loudly instead of silently repeating a response."""

    async def test_exhaustion_names_declared_responses(self) -> None:
        """Over-consuming raises ScriptExhaustedError carrying every label."""
        role = LLMTestRole(name="script-exhausted")
        script = MockScript.from_values(
            Value.from_text("only", name="metadata"),
            Value.from_text("second", name="chapters"),
        )

        async def consume_more_than_declared() -> None:
            """Ask the role once more than the script declares."""
            for position in range(3):
                await role.aask(question=_question(f"consume-{position}"))

        with pytest.raises(ScriptExhaustedError) as failure, script:
            await consume_more_than_declared()

        report = str(failure.value)
        assert "metadata" in report
        assert "chapters" in report
        assert "'llm'" in report

    async def test_padding_repeats_the_last_response(self) -> None:
        """with_padding absorbs extra calls by repeating the last response."""
        role = LLMTestRole(name="script-padding")
        with MockScript.from_texts("only").with_padding(2):
            answers = [await role.aask(question=_question(f"pad-{position}")) for position in range(3)]

        assert answers == ["only", "only", "only"]

    def test_install_without_values_raises(self) -> None:
        """An empty script is rejected before touching the router."""
        with pytest.raises(ValueError, match="at least one declared response"):
            MockScript.from_texts().install()

    def test_describe_lists_declared_responses(self) -> None:
        """Describe reports the group and every declared label."""
        script = MockScript.from_values(Value.from_text("x", name="alpha"), Value.from_text("y", name="beta"))
        report = script.describe()

        assert "alpha" in report
        assert "beta" in report
        assert "'llm'" in report


class TestMockScriptIsolation:
    """reset_on_exit and clear leave no responses behind."""

    async def test_reset_on_exit_empties_the_queue(self) -> None:
        """After a resetting block the group fails instead of replaying the script."""
        role = LLMTestRole(name="script-reset")
        with MockScript.from_texts("only", reset_on_exit=True):
            assert await role.aask(question=_question("reset")) == "only"

        with pytest.raises(RuntimeError, match="exhausted"):
            await role.aask(question=_question("after-reset"))

    async def test_clear_empties_the_group(self) -> None:
        """Clear drops queued responses so the next call fails loudly."""
        role = LLMTestRole(name="script-clear")
        script = MockScript.from_texts("only")
        script.install()
        script.clear()

        with pytest.raises(RuntimeError, match="exhausted"):
            await role.aask(question=_question("cleared"))

    def test_mutators_do_not_change_the_original(self) -> None:
        """Chained with_* calls return new scripts, leaving the receiver intact."""
        base = MockScript.from_texts("first")
        extended = base.with_text("second")

        assert len(base.values) == 1
        assert len(extended.values) == 2
        assert base.padding == 0
        assert base.with_padding(3).padding == 3
        assert base.group == "llm"
        assert base.with_group("other").group == "other"
        assert base.reset_on_exit is False
        assert base.with_reset_on_exit().reset_on_exit is True
