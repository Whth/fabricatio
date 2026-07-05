"""Shared helper functions used across CLI command modules."""

from collections.abc import Iterable
from pathlib import Path
from typing import NoReturn

import typer


def _exit_on_error(message: str) -> NoReturn:
    """Display an error message in red and exit with status 1."""
    typer.secho(message, fg=typer.colors.RED, bold=True)
    raise typer.Exit(code=1) from None


def _collect_files(patterns: Iterable[str]) -> list[Path]:
    """Expand glob patterns and literal file paths into a deduplicated, sorted file list.

    Raises typer.Exit if no valid files are found.
    """
    seen: set[Path] = set()
    for pat in patterns:
        matched = list(Path().glob(pat))
        if matched:
            for p in matched:
                resolved = p.resolve()
                if resolved.is_file():
                    seen.add(resolved)
        else:
            p = Path(pat).resolve()
            if not p.is_file():
                _exit_on_error(f"❌ No files matched pattern and not a file: {pat}")
            seen.add(p)
    files = sorted(seen)
    if not files:
        _exit_on_error("❌ No valid files found from provided patterns.")
    return files


def _resolve_text_or_file(
    text: str | None,
    file: Path | None,
    *,
    flag: str,
    file_desc: str | None = None,
    default: str | None = "",
    required: bool = False,
) -> str | None:
    """Resolve mutually exclusive text/file argument pair into a single value.

    Args:
        text: Direct text value from CLI option.
        file: Path to text file from CLI option.
        flag: CLI flag name without leading dashes (e.g. "outline", "illust-guideline").
        file_desc: Human-readable description for error messages. Defaults to ``flag``.
        default: Value when neither text nor file is provided. Use ``None`` for optional fields.
        required: If True, error when neither text nor file is provided.

    Returns:
        Resolved and stripped text, or default/None.
    """
    if file_desc is None:
        file_desc = flag
    if text is not None and file is not None:
        _exit_on_error(f"❌ Cannot use both --{flag} and --{flag}-file. Please use only one.")
    if text is None and file is None:
        if required:
            _exit_on_error(f"❌ Either --{flag} or --{flag}-file must be provided.")
        return default
    try:
        if file:
            return file.read_text(encoding="utf-8").strip()
        return text.strip()  # type: ignore[union-attr]
    except (OSError, IOError) as e:
        _exit_on_error(f"❌ Failed to read {file_desc} file: {e}")
