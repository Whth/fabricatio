"""Tests for fabricatio-capabilities model classes."""

import tempfile
from pathlib import Path
from typing import Dict, Optional

import orjson
import pytest
from fabricatio_capabilities.models.generic import (
    AsPrompt,
    FinalizedDumpAble,
    ModelHash,
    Patch,
    PersistentAble,
    SequencePatch,
    UpdateFrom,
    WordCount,
)
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Test helpers — concrete implementations of abstract classes
# ---------------------------------------------------------------------------


class _TestHashModel(ModelHash):
    """Concrete ModelHash for testing."""

    name: str = "test"


class _TestUpdateFrom(UpdateFrom, BaseModel):
    """Concrete UpdateFrom for testing."""

    value: int = 0

    def update_from_inner(self, other: "_TestUpdateFrom") -> "_TestUpdateFrom":
        self.value = other.value
        return self


class _TestFinalized(FinalizedDumpAble):
    """Concrete FinalizedDumpAble for testing."""

    name: str = "test"


class _SimpleModel(BaseModel):
    """Simple model for Patch testing."""

    name: str
    value: int


class _SimplePatch(Patch[_SimpleModel], BaseModel):
    """Concrete Patch for testing."""

    name: Optional[str] = None


class _TestSequencePatch(SequencePatch[str], BaseModel):
    """Concrete SequencePatch for testing."""

    pass


class StubPersistent(PersistentAble):
    """Concrete PersistentAble for testing."""

    name: str = "test"
    count: int = 42


class _TestAsPrompt(AsPrompt, BaseModel):
    """Concrete AsPrompt for testing."""

    text: str = "hello"

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {"text": self.text}


class _TestWordCount(WordCount):
    """Concrete WordCount for testing."""

    content: str = "hello world"
    expected_word_count: int = 2

    @property
    def exact_word_count(self) -> int:
        return len(self.content.split())


# ---------------------------------------------------------------------------
# ModelHash tests
# ---------------------------------------------------------------------------


class TestModelHash:
    """Tests for ModelHash.__hash__."""

    def test_hash_is_stable(self) -> None:
        """Test that __hash__ returns the same value for same data."""
        m1 = _TestHashModel(name="hello")
        m2 = _TestHashModel(name="hello")
        assert m1.__hash__() == m2.__hash__()

    def test_hash_differs_for_different_data(self) -> None:
        """Test that __hash__ differs for different data."""
        m1 = _TestHashModel(name="hello")
        m2 = _TestHashModel(name="world")
        assert m1.__hash__() != m2.__hash__()

    def test_hash_is_int(self) -> None:
        """Test that __hash__ returns an integer."""
        m = _TestHashModel(name="test")
        assert isinstance(m.__hash__(), int)

    def test_builtin_hash_works(self) -> None:
        """Test that builtin hash() works on ModelHash instances."""
        m = _TestHashModel(name="test")
        assert isinstance(hash(m), int)


# ---------------------------------------------------------------------------
# UpdateFrom tests
# ---------------------------------------------------------------------------


class TestUpdateFrom:
    """Tests for UpdateFrom."""

    def test_update_from_same_type(self) -> None:
        """Test updating from same type."""
        target = _TestUpdateFrom(value=1)
        source = _TestUpdateFrom(value=42)
        result = target.update_from(source)
        assert result is target
        assert target.value == 42

    def test_update_from_wrong_type_raises(self) -> None:
        """Test updating from wrong type raises."""
        target = _TestUpdateFrom(value=1)
        with pytest.raises((TypeError, ValueError)):
            target.update_from("not a model")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# FinalizedDumpAble tests
# ---------------------------------------------------------------------------


class TestFinalizedDumpAble:
    """Tests for FinalizedDumpAble."""

    def test_finalized_dump_returns_json(self) -> None:
        """Test finalized_dump returns valid JSON string."""
        obj = _TestFinalized(name="test")
        result = obj.finalized_dump()
        assert isinstance(result, str)
        data = orjson.loads(result)
        assert data["name"] == "test"

    def test_finalized_dump_to_file(self) -> None:
        """Test finalized_dump_to writes JSON to file."""
        obj = _TestFinalized(name="saved")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            result = obj.finalized_dump_to(path)
            assert result is obj
            assert path.exists()
            data = orjson.loads(path.read_text(encoding="utf-8"))
            assert data["name"] == "saved"


# ---------------------------------------------------------------------------
# Patch tests
# ---------------------------------------------------------------------------


class TestPatch:
    """Tests for Patch."""

    def test_apply_patch(self) -> None:
        """Test applying a patch to a model."""
        target = _SimpleModel(name="old", value=42)
        patch = _SimplePatch(name="new")
        result = patch.apply(target)
        assert result.name == "new"
        assert result.value == 42  # unchanged
        assert result is target

    def test_apply_patch_wrong_field_raises(self) -> None:
        """Test applying patch with field not in target raises."""

        class OtherModel(BaseModel):
            different: str = "x"

        class BadPatch(Patch[OtherModel], BaseModel):
            nonexistent: str = "y"

        target = OtherModel()
        patch = BadPatch(nonexistent="z")
        with pytest.raises(ValueError, match="not found"):
            patch.apply(target)

    def test_as_kwargs(self) -> None:
        """Test as_kwargs returns model dump."""
        patch = _SimplePatch(name="test")
        kwargs = patch.as_kwargs()
        assert isinstance(kwargs, dict)
        assert kwargs["name"] == "test"

    def test_ref_cls_default_none(self) -> None:
        """Test ref_cls returns None by default."""
        assert _SimplePatch.ref_cls() is None

    def test_excluded_fields_default_empty(self) -> None:
        """Test excluded_fields returns empty set by default."""
        assert _SimplePatch.excluded_fields() == set()

    def test_formated_json_schema(self) -> None:
        """Test formated_json_schema returns valid JSON."""
        schema_str = _SimplePatch.formated_json_schema()
        schema = orjson.loads(schema_str)
        assert "properties" in schema
        assert "name" in schema["properties"]

    def test_formated_json_schema_is_valid_json(self) -> None:
        """Test formated_json_schema returns parseable JSON."""
        schema_str = _SimplePatch.formated_json_schema()
        schema = orjson.loads(schema_str)
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_formated_json_schema_is_pretty_printed(self) -> None:
        """Test formated_json_schema returns indented JSON."""
        schema_str = _SimplePatch.formated_json_schema()
        assert "\n" in schema_str  # indented JSON has newlines


# ---------------------------------------------------------------------------
# SequencePatch tests
# ---------------------------------------------------------------------------


class TestSequencePatch:
    """Tests for SequencePatch."""

    def test_default_creates_empty_list(self) -> None:
        """Test default() creates an instance with empty tweaked list."""
        patch = _TestSequencePatch.default()
        assert patch.tweaked == []

    def test_update_from_inner_replaces_tweaked(self) -> None:
        """Test update_from_inner replaces tweaked list."""
        target = _TestSequencePatch(tweaked=["a", "b"])
        source = _TestSequencePatch(tweaked=["x", "y", "z"])
        result = target.update_from_inner(source)
        assert result is target
        assert target.tweaked == ["x", "y", "z"]

    def test_update_from_inner_empty_source(self) -> None:
        """Test update_from_inner with empty source clears tweaked."""
        target = _TestSequencePatch(tweaked=["a", "b"])
        source = _TestSequencePatch(tweaked=[])
        target.update_from_inner(source)
        assert target.tweaked == []


# ---------------------------------------------------------------------------
# PersistentAble tests
# ---------------------------------------------------------------------------


class TestPersistentAble:
    """Tests for PersistentAble."""

    def test_persist_to_directory(self) -> None:
        """Test persisting to a directory auto-generates filename."""
        obj = StubPersistent(name="dir_test")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = obj.persist(tmpdir)
            assert result is obj
            files = list(Path(tmpdir).glob("*.json"))
            assert len(files) == 1
            assert "StubPersistent_" in files[0].name

    def test_persist_and_load_roundtrip(self) -> None:
        """Test persist then from_persistent roundtrip."""
        obj = StubPersistent(name="loaded", count=77)
        with tempfile.TemporaryDirectory() as tmpdir:
            obj.persist(tmpdir)
            files = list(Path(tmpdir).glob("*.json"))
            assert len(files) == 1
            loaded = StubPersistent.from_persistent(files[0])
            assert loaded.name == "loaded"
            assert loaded.count == 77

    def test_from_latest_persistent(self) -> None:
        """Test loading latest from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            StubPersistent(name="first", count=1).persist(tmpdir)
            StubPersistent(name="second", count=2).persist(tmpdir)
            loaded = StubPersistent.from_latest_persistent(tmpdir)
            assert loaded is not None
            assert loaded.name in ("first", "second")

    def test_from_latest_persistent_empty_dir(self) -> None:
        """Test from_latest_persistent returns None for empty dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = StubPersistent.from_latest_persistent(tmpdir)
            assert result is None

    def test_from_latest_persistent_not_a_dir(self) -> None:
        """Test from_latest_persistent returns None for non-directory."""
        result = StubPersistent.from_latest_persistent("/nonexistent/path/that/does/not/exist")
        assert result is None


# ---------------------------------------------------------------------------
# AsPrompt tests
# ---------------------------------------------------------------------------


class TestAsPrompt:
    """Tests for AsPrompt."""

    def test_as_prompt_returns_string(self) -> None:
        """Test as_prompt returns a rendered string."""
        obj = _TestAsPrompt(text="world")
        result = obj.as_prompt()
        assert isinstance(result, str)
        assert "world" in result

    def test_as_prompt_different_data(self) -> None:
        """Test as_prompt with different data produces different output."""
        obj1 = _TestAsPrompt(text="alpha")
        obj2 = _TestAsPrompt(text="beta")
        assert obj1.as_prompt() != obj2.as_prompt()


# ---------------------------------------------------------------------------
# WordCount tests
# ---------------------------------------------------------------------------


class TestWordCount:
    """Tests for WordCount."""

    def test_expected_word_count(self) -> None:
        """Test expected_word_count field."""
        wc = _TestWordCount(content="hello world", expected_word_count=2)
        assert wc.expected_word_count == 2

    def test_exact_word_count(self) -> None:
        """Test exact_word_count property from concrete implementation."""
        wc = _TestWordCount(content="one two three four", expected_word_count=4)
        assert wc.exact_word_count == 4
