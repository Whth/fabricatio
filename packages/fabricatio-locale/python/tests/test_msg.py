"""Tests for the Msg class and Rust po file functions."""

from pathlib import Path

import pytest
from fabricatio_locale.rust import Msg, read_pofile, update_pofile


class TestMsg:
    """Test suite for the Msg class."""

    def test_msg_creation(self) -> None:
        """Test basic Msg creation."""
        msg = Msg(id="hello", txt="Hello")
        assert msg.id == "hello"
        assert msg.txt == "Hello"

    def test_msg_properties_are_strings(self) -> None:
        """Test that Msg properties return strings."""
        msg = Msg(id="key", txt="value")
        assert isinstance(msg.id, str)
        assert isinstance(msg.txt, str)

    def test_msg_empty_strings(self) -> None:
        """Test Msg with empty id and txt."""
        msg = Msg(id="", txt="")
        assert msg.id == ""
        assert msg.txt == ""

    def test_msg_special_characters(self) -> None:
        """Test Msg with special characters."""
        msg = Msg(id="key.with.dots", txt="Hello & welcome! 🎉")
        assert msg.id == "key.with.dots"
        assert msg.txt == "Hello & welcome! 🎉"

    def test_msg_unicode(self) -> None:
        """Test Msg with unicode content."""
        msg = Msg(id="greeting", txt="こんにちは世界")
        assert msg.id == "greeting"
        assert msg.txt == "こんにちは世界"

    def test_msg_multiline_txt(self) -> None:
        """Test Msg with multiline txt."""
        msg = Msg(id="multi", txt="line1\nline2\nline3")
        assert msg.txt == "line1\nline2\nline3"


PO_HEADER = r"""# Translation file.
# Copyright (C) 2024
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: test\n"
"PO-Revision-Date: 2024-01-01\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"""


def _write_po_file(path: Path, entries: list[tuple[str, str]]) -> None:
    """Write a minimal .po file with the given msgid/msgstr pairs."""
    lines = [PO_HEADER.strip()]
    for msgid, msgstr in entries:
        lines.append("")
        lines.append(f'msgid "{msgid}"')
        lines.append(f'msgstr "{msgstr}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestReadPofile:
    """Test suite for the read_pofile function."""

    def test_read_single_entry(self, tmp_path: Path) -> None:
        """Test reading a .po file with a single entry."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("Hello", "Bonjour")])

        result = read_pofile(po_file)
        assert len(result) == 1
        assert result[0].id == "Hello"
        assert result[0].txt == "Bonjour"

    def test_read_multiple_entries(self, tmp_path: Path) -> None:
        """Test reading a .po file with multiple entries."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("Hello", "Hola"), ("World", "Mundo"), ("Goodbye", "Adiós")])

        result = read_pofile(po_file)
        assert len(result) == 3
        assert result[0].id == "Hello"
        assert result[0].txt == "Hola"
        assert result[1].id == "World"
        assert result[1].txt == "Mundo"
        assert result[2].id == "Goodbye"
        assert result[2].txt == "Adiós"

    def test_read_empty_translation(self, tmp_path: Path) -> None:
        """Test reading a .po file with an empty msgstr."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("Hello", "")])

        result = read_pofile(po_file)
        assert len(result) == 1
        assert result[0].id == "Hello"
        assert result[0].txt == ""

    def test_read_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Test that reading a nonexistent .po file raises an error."""
        po_file = tmp_path / "nonexistent.po"
        with pytest.raises(RuntimeError):
            read_pofile(po_file)

    def test_read_returns_msg_instances(self, tmp_path: Path) -> None:
        """Test that read_pofile returns Msg instances."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("key", "value")])

        result = read_pofile(po_file)
        assert all(isinstance(m, Msg) for m in result)


class TestUpdatePofile:
    """Test suite for the update_pofile function."""

    def test_update_single_entry(self, tmp_path: Path) -> None:
        """Test updating a .po file with a single translated entry."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("Hello", "")])

        update_pofile(po_file, [Msg(id="Hello", txt="Bonjour")])

        result = read_pofile(po_file)
        assert len(result) >= 1
        # Find the Hello entry (skip header)
        hello = next(m for m in result if m.id == "Hello")
        assert hello.txt == "Bonjour"

    def test_update_preserves_unmodified(self, tmp_path: Path) -> None:
        """Test that update preserves entries not in the update set."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("Hello", "Hola"), ("World", "Mundo")])

        # Only update Hello
        update_pofile(po_file, [Msg(id="Hello", txt="Bonjour")])

        result = read_pofile(po_file)
        hello = next(m for m in result if m.id == "Hello")
        assert hello.txt == "Bonjour"

    def test_update_roundtrip(self, tmp_path: Path) -> None:
        """Test full read-update-read roundtrip."""
        po_file = tmp_path / "test.po"
        _write_po_file(po_file, [("Hello", ""), ("World", "")])

        # Read original
        original = read_pofile(po_file)

        # Create translated versions
        translated = [Msg(id=m.id, txt=f"TRANSLATED_{m.id}") for m in original]
        update_pofile(po_file, translated)

        # Read back
        updated = read_pofile(po_file)
        for msg in updated:
            if msg.id == "Hello":
                assert msg.txt == "TRANSLATED_Hello"
            elif msg.id == "World":
                assert msg.txt == "TRANSLATED_World"

    def test_update_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Test that updating a nonexistent .po file raises an error."""
        po_file = tmp_path / "nonexistent.po"
        with pytest.raises(RuntimeError):
            update_pofile(po_file, [Msg(id="key", txt="value")])
