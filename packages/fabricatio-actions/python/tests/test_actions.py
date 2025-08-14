"""Tests for the capabilities."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fabricatio_actions.actions.output import (
    DumpFinalizedOutput,
    Forward,
    GatherAsList,
    PersistentAll,
    RenderedDump,
    RetrieveFromLatest,
    RetrieveFromPersistent,
)
from fabricatio_capabilities.models.generic import FinalizedDumpAble, PersistentAble


class MockFinalizedDumpAble(FinalizedDumpAble):
    """Mock object that implements FinalizedDumpAble interface."""

    content: str

    def finalized_dump(self) -> str:
        """Finalize the dump of the object."""
        return self.content


class MockPersistentAble(PersistentAble):
    """Mock object that implements PersistentAble interface."""

    content: str


class TestDumpFinalizedOutput:
    """Tests for DumpFinalizedOutput action."""

    @pytest.mark.asyncio
    async def test_dump_with_explicit_path(self) -> None:
        """Test dumping with explicitly provided path."""
        action = DumpFinalizedOutput()
        mock_dumpable = MockFinalizedDumpAble(content="test content")

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "output.txt"
            result = await action._execute(mock_dumpable, dump_path=dump_path)

            assert result == dump_path.as_posix()
            assert dump_path.exists()
            assert dump_path.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_dump_with_configured_path(self) -> None:
        """Test dumping with pre-configured path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "configured.txt"
            action = DumpFinalizedOutput(dump_path=str(dump_path))
            mock_dumpable = MockFinalizedDumpAble(content="configured content")

            result = await action._execute(mock_dumpable)

            assert result == dump_path.as_posix()
            assert dump_path.exists()
            assert dump_path.read_text() == "configured content"


class TestRenderedDump:
    """Tests for RenderedDump action."""

    @pytest.mark.asyncio
    async def test_rendered_dump(self) -> None:
        """Test rendering and dumping with template."""
        action = RenderedDump(template_name="test_template")
        mock_dumpable = MockFinalizedDumpAble(content="template content")

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "rendered.txt"

            with patch("fabricatio_actions.actions.output.TEMPLATE_MANAGER") as mock_template:
                mock_template.render_template.return_value = "rendered: template content"

                result = await action._execute(mock_dumpable, dump_path=dump_path)

                assert result == dump_path.as_posix()
                assert dump_path.exists()
                assert dump_path.read_text() == "rendered: template content"
                mock_template.render_template.assert_called_once_with(
                    "test_template", {"MockFinalizedDumpAble": "template content"}
                )


class TestPersistentAll:
    """Tests for PersistentAll action."""

    @pytest.mark.asyncio
    async def test_persist_objects(self) -> None:
        """Test persisting multiple objects."""
        action = PersistentAll()

        with tempfile.TemporaryDirectory() as tmpdir:
            persist_dir = Path(tmpdir) / "persist"

            mock_obj1 = MockPersistentAble(content="obj1")
            mock_obj2 = MockPersistentAble(content="obj2")

            count = await action._execute(
                persist_dir=persist_dir, test_obj1=mock_obj1, test_obj2=mock_obj2, non_persistent="ignored"
            )

            assert count == 2
            assert persist_dir.exists()
            assert (persist_dir / "test_obj1").exists()
            assert len(list((persist_dir / "test_obj1").glob("*"))) == 1
            assert (persist_dir / "test_obj2").exists()
            assert len(list((persist_dir / "test_obj2").glob("*"))) == 1

    @pytest.mark.asyncio
    async def test_persist_collections(self) -> None:
        """Test persisting collections of objects."""
        action = PersistentAll()

        with tempfile.TemporaryDirectory() as tmpdir:
            persist_dir = Path(tmpdir) / "persist"

            mock_objs = [
                MockPersistentAble(content="item1"),
                MockPersistentAble(content="item2"),
                MockPersistentAble(content="item3"),
            ]

            count = await action._execute(persist_dir=persist_dir, collection=mock_objs)

            assert count == 3
            assert persist_dir.exists()

            assert (persist_dir / "collection").exists()
            assert len(list((persist_dir / "collection").glob("*"))) == 3

    @pytest.mark.asyncio
    async def test_persist_with_override(self) -> None:
        """Test persisting with override flag."""
        action = PersistentAll(override=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            persist_dir = Path(tmpdir) / "persist"
            persist_dir.mkdir()
            existing_file = persist_dir / "existing.txt"
            existing_file.write_text("existing")

            with patch.object(Path, "rmdir") as mock_rmdir:
                mock_obj = MockPersistentAble(content="new")
                count = await action._execute(persist_dir=persist_dir, test_obj=mock_obj)

                mock_rmdir.assert_called_once()
                assert count == 1


class TestRetrieveFromPersistent:
    """Tests for RetrieveFromPersistent action."""

    @pytest.mark.asyncio
    async def test_retrieve_from_file(self) -> None:
        """Test retrieving object from a single file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write("test content")
            tmp.flush()

            with patch.object(MockPersistentAble, "from_persistent") as mock_from_persistent:
                mock_from_persistent.return_value = MockPersistentAble(content="test content")

                action = RetrieveFromPersistent(load_path=tmp.name, retrieve_cls=MockPersistentAble)
                result = await action._execute()

                assert isinstance(result, MockPersistentAble)
                assert result.content == "test content"
                mock_from_persistent.assert_called_once_with(tmp.name)

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_path(self) -> None:
        """Test retrieving from non-existent path."""
        action = RetrieveFromPersistent(load_path="/nonexistent/path", retrieve_cls=MockPersistentAble)

        result = await action._execute()

        assert result is None


class TestRetrieveFromLatest:
    """Tests for RetrieveFromLatest action."""

    @pytest.mark.asyncio
    async def test_retrieve_latest_from_directory(self) -> None:
        """Test retrieving latest object from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files in the directory
            (Path(tmpdir) / "file1.txt").write_text("test1")
            (Path(tmpdir) / "file2.txt").write_text("test2")

            action = RetrieveFromLatest(load_path=tmpdir, retrieve_cls=MockPersistentAble)

            with patch.object(MockPersistentAble, "from_latest_persistent") as mock_from_latest:
                mock_from_latest.return_value = MockPersistentAble(content="latest")

                result = await action._execute()

                assert isinstance(result, MockPersistentAble)
                assert result.content == "latest"
                mock_from_latest.assert_called_once_with(tmpdir)

    @pytest.mark.asyncio
    async def test_retrieve_latest_from_file(self) -> None:
        """Test error when path is a file instead of directory."""
        with tempfile.NamedTemporaryFile() as tmp:
            action = RetrieveFromLatest(load_path=tmp.name, retrieve_cls=MockPersistentAble)

            result = await action._execute()

            assert result is None

    def test_from_mapping(self) -> None:
        """Test creating actions from mapping."""
        mapping = {"output1": "/path1", "output2": "/path2"}
        actions = RetrieveFromLatest.from_mapping(mapping, retrieve_cls=MockPersistentAble)

        assert len(actions) == 2
        assert actions[0].output_key == "output1"
        assert actions[0].load_path == "/path1"
        assert actions[1].output_key == "output2"
        assert actions[1].load_path == "/path2"


class TestGatherAsList:
    """Tests for GatherAsList action."""

    @pytest.mark.asyncio
    async def test_gather_by_suffix(self) -> None:
        """Test gathering objects by suffix."""
        action = GatherAsList(gather_suffix="_test")

        context = {"item1_test": "value1", "item2_test": "value2", "other_item": "ignored", "item3_test": "value3"}

        result = await action._execute(**context)

        assert len(result) == 3
        assert "value1" in result
        assert "value2" in result
        assert "value3" in result
        assert "ignored" not in result

    @pytest.mark.asyncio
    async def test_gather_by_prefix(self) -> None:
        """Test gathering objects by prefix."""
        action = GatherAsList(gather_prefix="test_")

        context = {"test_item1": "value1", "test_item2": "value2", "other_item": "ignored", "test_item3": "value3"}

        result = await action._execute(**context)

        assert len(result) == 3
        assert "value1" in result
        assert "value2" in result
        assert "value3" in result
        assert "ignored" not in result

    @pytest.mark.asyncio
    async def test_gather_suffix_priority(self) -> None:
        """Test that suffix takes priority over prefix."""
        action = GatherAsList(gather_suffix="_suf", gather_prefix="pre_")

        context = {"pre_item": "prefix_only", "item_suf": "suffix_only", "pre_item_suf": "both"}

        result = await action._execute(**context)

        assert len(result) == 2
        assert "suffix_only" in result
        assert "both" in result
        assert "prefix_only" not in result

    @pytest.mark.asyncio
    async def test_gather_no_criteria_error(self) -> None:
        """Test error when neither suffix nor prefix is provided."""
        action = GatherAsList()

        with pytest.raises(ValueError, match="Either `gather_suffix` or `gather_prefix` must be specified"):
            await action._execute(item1="value1")


class TestForward:
    """Tests for Forward action."""

    @pytest.mark.asyncio
    async def test_forward_existing_key(self) -> None:
        """Test forwarding an existing key."""
        action = Forward(original="source_key")

        context = {"source_key": "forwarded_value", "other_key": "ignored"}

        result = await action._execute(**context)

        assert result == "forwarded_value"

    @pytest.mark.asyncio
    async def test_forward_missing_key(self) -> None:
        """Test forwarding a missing key."""
        action = Forward(original="missing_key")

        context = {"other_key": "value"}
        result = await action._execute(**context)

        assert result is None

    def test_from_sequence(self) -> None:
        """Test creating Forward actions from sequence."""
        sequence = ["output1", "output2", "output3"]
        actions = Forward.from_sequence(sequence, original="source")

        assert len(actions) == 3
        assert all(action.original == "source" for action in actions)
        assert actions[0].output_key == "output1"
        assert actions[1].output_key == "output2"
        assert actions[2].output_key == "output3"

    def test_from_mapping_string_values(self) -> None:
        """Test creating Forward actions from mapping with string values."""
        mapping = {"key1": "output1", "key2": "output2"}
        actions = Forward.from_mapping(mapping)

        assert len(actions) == 2
        assert actions[0].original == "key1"
        assert actions[0].output_key == "output1"
        assert actions[1].original == "key2"
        assert actions[1].output_key == "output2"

    def test_from_mapping_sequence_values(self) -> None:
        """Test creating Forward actions from mapping with sequence values."""
        mapping = {"key1": ["output1", "output2"], "key2": ["output3"]}
        actions = Forward.from_mapping(mapping)

        assert len(actions) == 3
        assert actions[0].original == "key1"
        assert actions[0].output_key == "output1"
        assert actions[1].original == "key1"
        assert actions[1].output_key == "output2"
        assert actions[2].original == "key2"
        assert actions[2].output_key == "output3"
