"""Tests for the helper extensions: role composition, template stubs, value factories."""

from pathlib import Path
from uuid import uuid4

import orjson
import pytest
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.generic import SketchedAble
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import Value, return_obj_router_usage
from fabricatio_mock.models.mock_script import MockScript
from fabricatio_mock.utils import make_test_role, stub_template


class _ProposalModel(SketchedAble):
    """Sample model used to exercise the composed role's propose capability."""

    title: str


class TestMakeTestRole:
    """make_test_role composes LLMTestRole with capability mixins."""

    def test_composes_capability_mixins(self) -> None:
        """The returned instance mixes LLMTestRole and the requested capability."""
        role = make_test_role(Propose, name="deck")

        assert isinstance(role, LLMTestRole)
        assert isinstance(role, Propose)
        assert role.name == "deck"

    def test_reuses_one_composed_class(self) -> None:
        """Identical capability tuples share a memoized class."""
        assert type(make_test_role(Propose)) is type(make_test_role(Propose))

    def test_plain_role_keeps_llm_usage(self) -> None:
        """No capabilities still yields a role with LLM usage."""
        assert isinstance(make_test_role(name="plain"), UseLLM)

    async def test_composed_role_consumes_a_script(self) -> None:
        """A composed Propose role returns the scripted model end to end."""
        role = make_test_role(Propose, name="proposer")
        script = MockScript.from_values(Value.from_model(_ProposalModel(title="Chapter 1"), name="plan"))

        with script:
            proposal = await role.propose(_ProposalModel, f"outline {uuid4().hex}")

        assert proposal is not None
        assert proposal.title == "Chapter 1"


class TestStubTemplate:
    """stub_template installs a discoverable stub template."""

    def test_template_renders_after_install(self, tmp_path: Path) -> None:
        """The stub is registered under its file name and renders without CRLF."""
        name = stub_template("mock_stub_render", "HELLO {{who}}\nBYE", directory=tmp_path)

        rendered = TEMPLATE_MANAGER.render_template(name, {"who": "world"})

        assert rendered == "HELLO world\nBYE"

    def test_default_directory_is_temporary(self) -> None:
        """Without a directory the stub still registers and renders."""
        name = stub_template("mock_stub_tempdir", "VALUE {{value}}")

        assert TEMPLATE_MANAGER.render_template(name, {"value": "1"}) == "VALUE 1"


class TestValueFactories:
    """Value factories build the payloads tests used to hand-roll."""

    def test_from_text_renders_plain(self) -> None:
        """Plain text passes through with no fence or conversion."""
        assert Value.from_text("hello").to_string() == "hello"

    def test_from_raw_applies_convertor(self) -> None:
        """Raw values are rendered through their convertor."""
        assert Value.from_raw("hello", convertor=str.upper).to_string() == "HELLO"

    def test_from_model_serializes_pretty_json(self) -> None:
        """Model values serialize the aliased dump as JSON."""
        assert orjson.loads(Value.from_model(_ProposalModel(title="T")).to_string()) == {"title": "T"}

    def test_from_json_serializes_plain_object(self) -> None:
        """JSON values serialize objects without a fence."""
        assert orjson.loads(Value.from_json({"key": "val"}).to_string()) == {"key": "val"}

    def test_from_python_fences_code(self) -> None:
        """Python values are fenced as python blocks."""
        assert Value.from_python("x = 1").to_string() == "```python\nx = 1\n```"

    def test_from_generic_wraps_markers(self) -> None:
        """Generic values carry the Start/End markers."""
        assert Value.from_generic("body").to_string() == "--- Start of string ---\nbody\n--- End of string ---"

    def test_name_is_carried_for_reports(self) -> None:
        """The optional name is stored on the value for script reports."""
        assert Value.from_text("x", name="metadata").name == "metadata"


class TestReturnObjRouterUsage:
    """return_obj_router_usage emits unfenced JSON payloads."""

    def test_payload_is_raw_json(self) -> None:
        """The first response parses as JSON without fence stripping."""
        responses = return_obj_router_usage(["a", "b"], padding=0)

        assert orjson.loads(responses[0]) == ["a", "b"]

    def test_padding_is_applied(self) -> None:
        """Padding repeats the last payload for retry safety."""
        responses = return_obj_router_usage({"key": "val"}, padding=2)

        assert len(responses) == 3

    def test_empty_raises(self) -> None:
        """No objects raises ValueError."""
        with pytest.raises(ValueError, match="At least one object"):
            return_obj_router_usage()
