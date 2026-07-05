"""Reusable ``typer.Option(...)`` constants shared by multiple commands.

Each command that writes a novel accepts the same outline / output / styling /
guidance / persist-dir parameters. Centralizing the option declarations here
keeps the envvar names, default values, and help text consistent across every
``write_*`` command without forcing a custom decorator.

Usage:

    from fabricatio_novel.commands._options import OUTLINE, OUTPUT_PATH

    @app.command(name="w")
    def write_novel(
        outline: str = OUTLINE,
        output_path: Path = OUTPUT_PATH,
    ) -> None:
        ...
"""

import typer

# --- Outline ---------------------------------------------------------------
OUTLINE: typer.Option = typer.Option(
    None, "--outline", "-o", help="The novel's outline or premise.", envvar="NOVEL_OUTLINE"
)
"""``--outline/-o`` — the novel's outline/premise (or read from ``--outline-file``)."""

OUTLINE_FILE: typer.Option = typer.Option(
    None,
    "--outline-file",
    "-of",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to a text file containing the novel outline.",
    envvar="NOVEL_OUTLINE_FILE",
)
"""``--outline-file/-of`` — file containing the novel outline."""

# --- Output / styling ------------------------------------------------------
OUTPUT_PATH: typer.Option = typer.Option(
    "./novel.epub", "--output", "-out", dir_okay=False, help="Output EPUB file path.", envvar="NOVEL_OUTPUT_PATH"
)
"""``--output/-out`` — destination EPUB path."""

FONT_FILE: typer.Option = typer.Option(
    None,
    "--font",
    "-f",
    exists=True,
    dir_okay=False,
    help="Path to custom font file (TTF).",
    envvar="NOVEL_FONT_FILE",
)
"""``--font/-f`` — custom font file for the generated EPUB."""

COVER_IMAGE: typer.Option = typer.Option(
    None,
    "--cover",
    "-c",
    exists=True,
    dir_okay=False,
    help="Path to cover image (PNG/JPG/WEBP).",
    envvar="NOVEL_COVER_IMAGE",
)
"""``--cover/-c`` — cover image for the generated EPUB."""

LANGUAGE: typer.Option = typer.Option(
    "English", "--lang", "-l", help="Language of the novel (e.g., 简体中文, English, jp).", envvar="NOVEL_LANGUAGE"
)
"""``--lang/-l`` — language the novel is written in."""

# --- Chapter guidance ------------------------------------------------------
CHAPTER_GUIDANCE: typer.Option = typer.Option(
    None, "--guidance", "-g", help="Guidelines for chapter generation.", envvar="NOVEL_CHAPTER_GUIDANCE"
)
"""``--guidance/-g`` — guidelines for chapter generation."""

GUIDANCE_FILE: typer.Option = typer.Option(
    None,
    "--guidance-file",
    "-gf",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to a text file containing chapter generation guidelines.",
    envvar="NOVEL_GUIDANCE_FILE",
)
"""``--guidance-file/-gf`` — file containing chapter generation guidelines."""

# --- Persistence -----------------------------------------------------------
PERSIST_DIR: typer.Option = typer.Option(
    "./persist", "--persist-dir", help="Directory to save intermediate states.", envvar="NOVEL_PERSIST_DIR"
)
"""``--persist-dir`` — directory for intermediate workflow outputs."""
