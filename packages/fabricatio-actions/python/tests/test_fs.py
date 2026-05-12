"""Test module for fabricatio-actions file system actions.

This module contains pytest test cases verifying the correctness of ReadText,
DumpText, SmartReadText, and SmartDumpText actions, plus FromMapping/FromSequence
abstract base classes.
"""

import tempfile
from pathlib import Path

import pytest
from fabricatio_actions.actions.fs import DumpText, ReadText, SmartDumpText, SmartReadText
from fabricatio_core import Task
from fabricatio_mock.models.mock_role import LLMTestRole

# ---------------------------------------------------------------------------
# Capability test roles
# ---------------------------------------------------------------------------


class SmartReadRole(LLMTestRole, SmartReadText):
    """Test role combining LLMTestRole with SmartReadText for testing."""


class SmartDumpRole(LLMTestRole, SmartDumpText):
    """Test role combining LLMTestRole with SmartDumpText for testing."""


# ---------------------------------------------------------------------------
# Tests: ReadText
# ---------------------------------------------------------------------------


class TestReadText:
    """Test suite for the ReadText action."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self) -> None:
        """Test reading text from an existing file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("Hello, world!")
            tmp.flush()
            path = tmp.name

        action = ReadText(read_path=path)
        result = await action._execute()
        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_read_empty_file(self) -> None:
        """Test reading from an empty file returns empty string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("")
            tmp.flush()
            path = tmp.name

        action = ReadText(read_path=path)
        result = await action._execute()
        assert result == ""

    @pytest.mark.asyncio
    async def test_read_multiline_file(self) -> None:
        """Test reading a file with multiple lines preserves content."""
        content = "line1\nline2\nline3"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            path = tmp.name

        action = ReadText(read_path=path)
        result = await action._execute()
        assert result == content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self) -> None:
        """Test that reading a non-existent file raises FileNotFoundError."""
        action = ReadText(read_path="/nonexistent/path/file.txt")
        with pytest.raises(FileNotFoundError):
            await action._execute()

    @pytest.mark.asyncio
    async def test_read_with_pathlib_path(self) -> None:
        """Test reading using a Path object instead of string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("pathlib test")
            tmp.flush()
            path = Path(tmp.name)

        action = ReadText(read_path=path)
        result = await action._execute()
        assert result == "pathlib test"

    def test_from_mapping(self) -> None:
        """Test creating ReadText actions from a mapping."""
        mapping = {"output1": "/path/a.txt", "output2": "/path/b.txt"}
        actions = ReadText.from_mapping(mapping)

        assert len(actions) == 2
        assert actions[0].output_key == "output1"
        assert actions[0].read_path == "/path/a.txt"
        assert actions[1].output_key == "output2"
        assert actions[1].read_path == "/path/b.txt"

    def test_from_mapping_with_path_objects(self) -> None:
        """Test from_mapping with Path values."""
        mapping = {"out": Path("/some/path.txt")}
        actions = ReadText.from_mapping(mapping)

        assert len(actions) == 1
        assert actions[0].read_path == Path("/some/path.txt")


# ---------------------------------------------------------------------------
# Tests: DumpText
# ---------------------------------------------------------------------------


class TestDumpText:
    """Test suite for the DumpText action."""

    @pytest.mark.asyncio
    async def test_dump_text(self) -> None:
        """Test dumping text to a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "output.txt"
            action = DumpText(dump_path=dump_path, text_key="my_text")

            await action._execute(my_text="Hello, dump!")

            assert dump_path.exists()
            assert dump_path.read_text(encoding="utf-8") == "Hello, dump!"

    @pytest.mark.asyncio
    async def test_dump_creates_parent_dirs(self) -> None:
        """Test that DumpText creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "subdir" / "nested" / "output.txt"
            action = DumpText(dump_path=dump_path, text_key="text")

            await action._execute(text="nested content")

            assert dump_path.exists()
            assert dump_path.read_text(encoding="utf-8") == "nested content"

    @pytest.mark.asyncio
    async def test_dump_overwrites_existing(self) -> None:
        """Test that dumping overwrites an existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "output.txt"
            dump_path.write_text("old content", encoding="utf-8")

            action = DumpText(dump_path=dump_path, text_key="text")
            await action._execute(text="new content")

            assert dump_path.read_text(encoding="utf-8") == "new content"

    @pytest.mark.asyncio
    async def test_dump_missing_key_raises(self) -> None:
        """Test that dumping with a missing context key raises an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "output.txt"
            action = DumpText(dump_path=dump_path, text_key="missing_key")

            with pytest.raises(ValueError, match="not found"):
                await action._execute(other_key="value")

    @pytest.mark.asyncio
    async def test_dump_default_text_key(self) -> None:
        """Test that default text_key is 'text'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "output.txt"
            action = DumpText(dump_path=dump_path)

            await action._execute(text="default key content")

            assert dump_path.read_text(encoding="utf-8") == "default key content"

    def test_from_mapping(self) -> None:
        """Test creating DumpText actions from a mapping."""
        mapping = {"source_key1": "/path/out1.txt", "source_key2": "/path/out2.txt"}
        actions = DumpText.from_mapping(mapping)

        assert len(actions) == 2
        assert actions[0].text_key == "source_key1"
        assert actions[0].dump_path == "/path/out1.txt"
        assert actions[1].text_key == "source_key2"
        assert actions[1].dump_path == "/path/out2.txt"


# ---------------------------------------------------------------------------
# Tests: SmartReadText (with pre-set path, no LLM call)
# ---------------------------------------------------------------------------


class TestSmartReadText:
    """Test suite for the SmartReadText action."""

    @pytest.fixture
    def role(self) -> SmartReadRole:
        """Create a SmartReadRole instance.

        Returns:
            SmartReadRole: SmartReadRole instance
        """
        return SmartReadRole()

    @pytest.fixture
    def sample_task(self) -> Task[str]:
        """Create a sample Task for testing.

        Returns:
            Task[str]: A task with a briefing.
        """
        return Task(name="test_read", description="Read the config file.")

    @pytest.mark.asyncio
    async def test_smart_read_with_preset_path(self, role: SmartReadRole, sample_task: Task[str]) -> None:
        """Test SmartReadText reads correctly when read_path is pre-set (skips LLM)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("smart read content")
            tmp.flush()
            path = tmp.name

        role.read_path = path
        result = await role._execute(task_input=sample_task)
        assert result == "smart read content"

    @pytest.mark.asyncio
    async def test_smart_read_inherits_read_text(self, role: SmartReadRole, sample_task: Task[str]) -> None:
        """Test SmartReadText inherits ReadText behavior for actual file reading."""
        content = "line1\nline2\nline3"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            path = tmp.name

        role.read_path = path
        result = await role._execute(task_input=sample_task)
        assert result == content


# ---------------------------------------------------------------------------
# Tests: SmartDumpText (with pre-set path, no LLM call)
# ---------------------------------------------------------------------------


class TestSmartDumpText:
    """Test suite for the SmartDumpText action."""

    @pytest.fixture
    def role(self) -> SmartDumpRole:
        """Create a SmartDumpRole instance.

        Returns:
            SmartDumpRole: SmartDumpRole instance
        """
        return SmartDumpRole()

    @pytest.fixture
    def sample_task(self) -> Task[str]:
        """Create a sample Task for testing.

        Returns:
            Task[str]: A task with a briefing.
        """
        return Task(name="test_dump", description="Write the output file.")

    @pytest.mark.asyncio
    async def test_smart_dump_with_preset_path(self, role: SmartDumpRole, sample_task: Task[str]) -> None:
        """Test SmartDumpText writes correctly when dump_path is pre-set (skips LLM)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "smart_output.txt"
            role.dump_path = dump_path
            role.text_key = "content"

            await role._execute(task_input=sample_task, content="smart dump content")

            assert dump_path.exists()
            assert dump_path.read_text(encoding="utf-8") == "smart dump content"

    @pytest.mark.asyncio
    async def test_smart_dump_creates_dirs(self, role: SmartDumpRole, sample_task: Task[str]) -> None:
        """Test SmartDumpText creates parent directories like DumpText."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "nested" / "dir" / "output.txt"
            role.dump_path = dump_path
            role.text_key = "text"

            await role._execute(task_input=sample_task, text="nested smart dump")

            assert dump_path.exists()
            assert dump_path.read_text(encoding="utf-8") == "nested smart dump"


# ---------------------------------------------------------------------------
# Tests: FromMapping / FromSequence (abstract base classes)
# ---------------------------------------------------------------------------


class TestFromMapping:
    """Test suite for FromMapping abstract base class via concrete implementations."""

    def test_read_text_from_mapping(self) -> None:
        """Test FromMapping is implemented by ReadText."""
        from fabricatio_actions.models.generic import FromMapping

        assert issubclass(ReadText, FromMapping)

    def test_dump_text_from_mapping(self) -> None:
        """Test FromMapping is implemented by DumpText."""
        from fabricatio_actions.models.generic import FromMapping

        assert issubclass(DumpText, FromMapping)

    def test_forward_from_mapping(self) -> None:
        """Test FromMapping is implemented by Forward."""
        from fabricatio_actions.actions.output import Forward
        from fabricatio_actions.models.generic import FromMapping

        assert issubclass(Forward, FromMapping)


class TestFromSequence:
    """Test suite for FromSequence abstract base class via concrete implementations."""

    def test_forward_from_sequence(self) -> None:
        """Test FromSequence is implemented by Forward."""
        from fabricatio_actions.actions.output import Forward
        from fabricatio_actions.models.generic import FromSequence

        assert issubclass(Forward, FromSequence)
