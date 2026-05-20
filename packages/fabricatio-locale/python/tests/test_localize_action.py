"""Tests for the LocalizePoFile action."""

import shutil
from pathlib import Path

import pytest
from fabricatio_locale.actions.localize import LocalizePoFile
from fabricatio_locale.rust import read_pofile
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_generic_router_usage
from fabricatio_mock.utils import install_router_usage


class LocalizePoFileRole(LLMTestRole, LocalizePoFile):
    """Test role combining LLMTestRole with LocalizePoFile."""


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


@pytest.mark.asyncio
async def test_localize_po_file_action(tmp_path: Path) -> None:
    """Test LocalizePoFile end-to-end: read po, localize, write back."""
    po_file = tmp_path / "messages.po"
    output_file = tmp_path / "messages_fr.po"
    _write_po_file(po_file, [("Hello", ""), ("World", "")])
    # update_pofile reads and writes the same file; pre-copy to output path
    shutil.copy2(po_file, output_file)

    responses = return_generic_router_usage("Bonjour", "Monde")
    with install_router_usage(*responses):
        action = LocalizePoFileRole(
            pofile=str(po_file),
            target_lang="fr",
            output_path=str(output_file),
        )
        result_path = await action._execute()

        assert result_path == output_file
        assert output_file.exists()

        result = read_pofile(output_file)
        hello = next(m for m in result if m.id == "Hello")
        world = next(m for m in result if m.id == "World")
        assert hello.txt == "Bonjour"
        assert world.txt == "Monde"


@pytest.mark.asyncio
async def test_localize_po_file_overwrites_input(tmp_path: Path) -> None:
    """Test LocalizePoFile with output_path=None writes back to input file."""
    po_file = tmp_path / "messages.po"
    _write_po_file(po_file, [("Hello", "")])

    responses = return_generic_router_usage("Hola")
    with install_router_usage(*responses):
        action = LocalizePoFileRole(
            pofile=str(po_file),
            target_lang="es",
            output_path=None,
        )
        result_path = await action._execute()

        assert result_path == po_file
        result = read_pofile(po_file)
        hello = next(m for m in result if m.id == "Hello")
        assert hello.txt == "Hola"


@pytest.mark.asyncio
async def test_localize_po_file_preserves_ids(tmp_path: Path) -> None:
    """Test that LocalizePoFile preserves message IDs after localization."""
    po_file = tmp_path / "messages.po"
    output_file = tmp_path / "out.po"
    _write_po_file(po_file, [("greeting", ""), ("farewell", "")])
    shutil.copy2(po_file, output_file)

    responses = return_generic_router_usage("Guten Tag", "Auf Wiedersehen")
    with install_router_usage(*responses):
        action = LocalizePoFileRole(
            pofile=str(po_file),
            target_lang="de",
            output_path=str(output_file),
        )
        await action._execute()

        result = read_pofile(output_file)
        ids = [m.id for m in result]
        assert "greeting" in ids
        assert "farewell" in ids
