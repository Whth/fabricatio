"""Tests for the fabricatio-mock package.

This module contains comprehensive tests for all mock utilities,
including Value serialization, router response helpers, role defaults,
and integration with the dummy router.
"""

import orjson
import pytest
from fabricatio_core import Role
from fabricatio_mock import DUMMY_LLM_GROUP
from fabricatio_mock.models.mock_role import LLMTestRole, ProposeTestRole
from fabricatio_mock.models.mock_router import (
    Value,
    pad_embeddings,
    pad_rankings,
    pad_responses,
    return_code_router_usage,
    return_generic_router_usage,
    return_json_obj_router_usage,
    return_json_router_usage,
    return_mixed_router_usage,
    return_model_json_router_usage,
    return_python_router_usage,
    return_router_usage,
)
from fabricatio_mock.utils import (
    code_block,
    generic_block,
    make_n_roles,
    make_roles,
)
from pydantic import BaseModel

# =============================================================================
# Utils: code_block / generic_block
# =============================================================================


class TestCodeBlock:
    """Tests for the code_block utility."""

    def test_default_lang_json(self) -> None:
        """Default lang is json and wraps content in fenced block."""
        result = code_block('{"key": "value"}')
        assert result == '```json\n{"key": "value"}\n```'

    def test_custom_lang(self) -> None:
        """Custom lang parameter is reflected in the fence."""
        result = code_block("print('hi')", lang="python")
        assert result == "```python\nprint('hi')\n```"

    def test_empty_content(self) -> None:
        """Empty string still produces a valid fenced block."""
        result = code_block("")
        assert result == "```json\n\n```"


class TestGenericBlock:
    """Tests for the generic_block utility."""

    def test_default_lang(self) -> None:
        """Default lang is String with Start/End markers."""
        result = generic_block("hello")
        assert result == "--- Start of String ---\nhello\n--- End of String ---"

    def test_custom_lang(self) -> None:
        """Custom lang is reflected in the Start/End markers."""
        result = generic_block("data", lang="Output")
        assert result == "--- Start of Output ---\ndata\n--- End of Output ---"

    def test_multiline_content(self) -> None:
        """Multiline content is preserved between markers."""
        result = generic_block("line1\nline2")
        expected = "--- Start of String ---\nline1\nline2\n--- End of String ---"
        assert result == expected


# =============================================================================
# Utils: make_roles / make_n_roles
# =============================================================================


class TestMakeRoles:
    """Tests for make_roles and make_n_roles."""

    def test_make_roles_returns_correct_count(self) -> None:
        """Role count matches input name list length."""
        roles = make_roles(["a", "b", "c"])
        assert len(roles) == 3

    def test_make_roles_names(self) -> None:
        """Each role receives the corresponding name."""
        roles = make_roles(["alpha", "beta"])
        assert [r.name for r in roles] == ["alpha", "beta"]

    def test_make_roles_all_have_description(self) -> None:
        """All roles get the default description."""
        roles = make_roles(["x"])
        assert all(r.description == "test" for r in roles)

    def test_make_roles_custom_cls(self) -> None:
        """Custom role_cls is used instead of base Role."""
        roles = make_roles(["r1"], role_cls=LLMTestRole)
        assert all(isinstance(r, LLMTestRole) for r in roles)

    def test_make_n_roles_count(self) -> None:
        """Requested count is honoured."""
        roles = make_n_roles(5)
        assert len(roles) == 5

    def test_make_n_roles_naming(self) -> None:
        """Roles are named 'Role 1', 'Role 2', etc."""
        roles = make_n_roles(3)
        assert [r.name for r in roles] == ["Role 1", "Role 2", "Role 3"]

    def test_make_n_roles_zero(self) -> None:
        """Zero count yields an empty list."""
        roles = make_n_roles(0)
        assert roles == []

    def test_make_roles_empty(self) -> None:
        """Empty name list yields an empty list."""
        roles = make_roles([])
        assert roles == []


# =============================================================================
# Mock Router: _pad_responses
# =============================================================================


class TestPadResponses:
    """Tests for _pad_responses helper."""

    def test_single_value(self) -> None:
        """Single value is padded to 11 entries with copies of itself."""
        result = pad_responses("hello")
        assert result[0] == "hello"
        assert len(result) == 11  # 1 + 10 padding

    def test_multiple_values(self) -> None:
        """Last value is used as padding default."""
        result = pad_responses("a", "b", "c")
        assert result[:3] == ["a", "b", "c"]
        assert all(r == "c" for r in result[3:])

    def test_custom_default(self) -> None:
        """Explicit default overrides the last value for padding."""
        result = pad_responses("a", "b", default="fallback")
        assert result[:2] == ["a", "b"]
        assert all(r == "fallback" for r in result[2:])

    def test_empty_raises(self) -> None:
        """No arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one value"):
            pad_responses()


# =============================================================================
# Mock Router: return_router_usage
# =============================================================================


class TestReturnRouterUsage:
    """Tests for return_router_usage and typed variants."""

    def test_basic_return(self) -> None:
        """Single response is first element, padded to 11."""
        result = return_router_usage("hi")
        assert result[0] == "hi"
        assert len(result) == 11

    def test_multiple_responses(self) -> None:
        """Multiple responses appear in order."""
        result = return_router_usage("a", "b")
        assert result[0] == "a"
        assert result[1] == "b"

    def test_return_python_router_usage(self) -> None:
        """Response is wrapped in a python fenced code block."""
        result = return_python_router_usage("print(1)")
        assert result[0] == "```python\nprint(1)\n```"

    def test_return_json_router_usage(self) -> None:
        """Response is wrapped in a json fenced code block."""
        result = return_json_router_usage('{"k": "v"}')
        assert result[0] == '```json\n{"k": "v"}\n```'

    def test_return_json_obj_router_usage(self) -> None:
        """Python dict is serialized and wrapped in a json code block."""
        result = return_json_obj_router_usage({"key": "val"})
        # Output is wrapped in ```json ... ``` code blocks
        inner = result[0].removeprefix("```json\n").removesuffix("\n```")
        parsed = orjson.loads(inner)
        assert parsed == {"key": "val"}

    def test_return_json_obj_empty_raises(self) -> None:
        """No arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one array"):
            return_json_obj_router_usage()

    def test_return_generic_router_usage(self) -> None:
        """Response is wrapped in a generic Start/End block."""
        result = return_generic_router_usage("content")
        assert result[0] == "--- Start of string ---\ncontent\n--- End of string ---"

    def test_return_generic_router_usage_custom_lang(self) -> None:
        """Custom lang appears in the Start/End markers."""
        result = return_generic_router_usage("data", lang="Output")
        assert "Start of Output" in result[0]

    def test_return_generic_router_usage_empty_raises(self) -> None:
        """No arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one string"):
            return_generic_router_usage()

    def test_return_code_router_usage_empty_raises(self) -> None:
        """No code arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one code"):
            return_code_router_usage(lang="python")


# =============================================================================
# Mock Router: Value
# =============================================================================


class _SampleModel(BaseModel):
    name: str
    value: int


class TestValue:
    """Tests for the Value dataclass."""

    def test_model_type(self) -> None:
        """Pydantic model is serialized to pretty-printed JSON."""
        m = _SampleModel(name="test", value=42)
        v = Value(source=m, type="model")
        result = v.to_string()
        parsed = orjson.loads(result)
        assert parsed == {"name": "test", "value": 42}

    def test_json_type(self) -> None:
        """Dict source is serialized as JSON."""
        v = Value(source={"key": "val"}, type="json")
        result = v.to_string()
        assert orjson.loads(result) == {"key": "val"}

    def test_python_type(self) -> None:
        """Python source is wrapped in a fenced code block."""
        v = Value(source="x = 1", type="python")
        result = v.to_string()
        assert result == "```python\nx = 1\n```"

    def test_generic_type(self) -> None:
        """Generic source is wrapped with Start/End markers."""
        v = Value(source="hello", type="generic")
        result = v.to_string()
        assert "Start of string" in result
        assert "hello" in result

    def test_raw_type_with_convertor(self) -> None:
        """Raw source is processed through the convertor."""
        v = Value(source="anything", type="raw", convertor=lambda s: f"RAW:{s}")
        assert v.to_string() == "RAW:anything"

    def test_raw_type_without_convertor_raises(self) -> None:
        """Raw type without convertor raises ValueError."""
        v = Value(source="anything", type="raw")
        with pytest.raises(ValueError, match="Invalid type"):
            v.to_string()

    def test_model_type_with_non_model_raises(self) -> None:
        """Non-model source with model type raises ValueError."""
        v = Value(source="not a model", type="model")
        with pytest.raises(ValueError, match="Invalid type"):
            v.to_string()


# =============================================================================
# Mock Router: return_mixed_router_usage / return_model_json_router_usage
# =============================================================================


class TestMixedAndModelRouterUsage:
    """Tests for mixed and model-specific router usage helpers."""

    def test_return_model_json_router_usage(self) -> None:
        """Test that a model is correctly serialized and returned via JSON router."""
        m = _SampleModel(name="x", value=1)
        result = return_model_json_router_usage(m)
        inner = result[0].removeprefix("```json\n").removesuffix("\n```")
        parsed = orjson.loads(inner)
        assert parsed == {"name": "x", "value": 1}

    def test_return_model_json_router_usage_empty_raises(self) -> None:
        """Test that calling without arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one model"):
            return_model_json_router_usage()

    def test_return_mixed_router_usage(self) -> None:
        """Test that mixed model and generic values are correctly returned."""
        m = _SampleModel(name="a", value=2)
        values = [
            Value(source=m, type="model"),
            Value(source="hi", type="generic"),
        ]
        result = return_mixed_router_usage(*values)
        assert orjson.loads(result[0]) == {"name": "a", "value": 2}
        assert "hi" in result[1]


# =============================================================================
# Mock Role: defaults
# =============================================================================


class TestMockRoleDefaults:
    """Tests for LLMTestRole and ProposeTestRole default values."""

    def test_llm_test_role_send_to(self) -> None:
        """Verify LLMTestRole defaults to DUMMY_LLM_GROUP for send_to."""
        role = LLMTestRole()
        assert role.llm_send_to == DUMMY_LLM_GROUP

    def test_llm_test_role_no_cache(self) -> None:
        """Verify LLMTestRole defaults llm_no_cache to True."""
        role = LLMTestRole()
        assert role.llm_no_cache is True

    def test_propose_test_role_inherits_defaults(self) -> None:
        """Verify ProposeTestRole inherits llm_send_to and llm_no_cache defaults."""
        role = ProposeTestRole()
        assert role.llm_send_to == DUMMY_LLM_GROUP
        assert role.llm_no_cache is True

    def test_propose_test_role_is_role(self) -> None:
        """Verify ProposeTestRole is an instance of Role."""
        role = ProposeTestRole()
        assert isinstance(role, Role)


# =============================================================================
# Mock Router: pad_embeddings / pad_rankings
# =============================================================================


class TestPadEmbeddings:
    """Tests for pad_embeddings helper."""

    def test_single_embedding(self) -> None:
        """Single embedding is padded to 11 entries."""
        result = pad_embeddings([1.0, 2.0, 3.0])
        assert result[0] == [1.0, 2.0, 3.0]
        assert len(result) == 11

    def test_multiple_embeddings(self) -> None:
        """Last embedding is used as padding default."""
        e1 = [1.0, 0.0]
        e2 = [0.0, 1.0]
        result = pad_embeddings(e1, e2)
        assert result[:2] == [e1, e2]
        assert all(r == e2 for r in result[2:])

    def test_custom_default(self) -> None:
        """Explicit default overrides the last embedding for padding."""
        fallback = [0.5, 0.5]
        result = pad_embeddings([1.0, 2.0], default=fallback)
        assert result[0] == [1.0, 2.0]
        assert all(r == fallback for r in result[1:])

    def test_empty_raises(self) -> None:
        """No arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one embedding"):
            pad_embeddings()

    def test_custom_padding(self) -> None:
        """Custom padding count is honoured."""
        result = pad_embeddings([1.0], padding=3)
        assert len(result) == 4  # 1 + 3


class TestPadRankings:
    """Tests for pad_rankings helper."""

    def test_single_ranking(self) -> None:
        """Single ranking is padded to 11 entries."""
        result = pad_rankings((0, 0.9))
        assert result[0] == (0, 0.9)
        assert len(result) == 11

    def test_multiple_rankings(self) -> None:
        """Last ranking is used as padding default."""
        r1 = (0, 0.9)
        r2 = (1, 0.5)
        result = pad_rankings(r1, r2)
        assert result[:2] == [r1, r2]
        assert all(r == r2 for r in result[2:])

    def test_custom_default(self) -> None:
        """Explicit default overrides the last ranking for padding."""
        fallback = (99, 0.0)
        result = pad_rankings((0, 0.8), default=fallback)
        assert result[0] == (0, 0.8)
        assert all(r == fallback for r in result[1:])

    def test_empty_raises(self) -> None:
        """No arguments raises ValueError."""
        with pytest.raises(ValueError, match="At least one ranking"):
            pad_rankings()

    def test_custom_padding(self) -> None:
        """Custom padding count is honoured."""
        result = pad_rankings((0, 1.0), padding=5)
        assert len(result) == 6  # 1 + 5


class TestSetupDummyEmbeddings:
    """Tests for setup_dummy_embeddings integration."""

    def test_imports_available(self) -> None:
        """Verify new constants are importable."""
        from fabricatio_mock import DUMMY_EMBEDDING_GROUP, DUMMY_RERANKER_GROUP

        assert DUMMY_EMBEDDING_GROUP == "embedding"
        assert DUMMY_RERANKER_GROUP == "reranker"

    def test_setup_dummy_embeddings_callable(self) -> None:
        """setup_dummy_embeddings is callable without error."""
        from fabricatio_mock.utils import setup_dummy_embeddings

        # Should not raise
        setup_dummy_embeddings([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])

    def test_setup_dummy_reranks_callable(self) -> None:
        """setup_dummy_reranks is callable without error."""
        from fabricatio_mock.utils import setup_dummy_reranks

        # Should not raise
        setup_dummy_reranks((0, 0.9), (1, 0.5))

    def test_install_dummy_embeddings_context_manager(self) -> None:
        """install_dummy_embeddings context manager yields without error."""
        from fabricatio_mock.utils import install_dummy_embeddings

        with install_dummy_embeddings([0.1, 0.2, 0.3]):
            pass

    def test_install_dummy_reranks_context_manager(self) -> None:
        """install_dummy_reranks context manager yields without error."""
        from fabricatio_mock.utils import install_dummy_reranks

        with install_dummy_reranks((0, 0.95)):
            pass
