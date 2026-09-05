"""Default EPUB styling shared by ``dump_epub``."""

__all__ = ["DEFAULT_EPUB_CSS"]

_ILLUSTRATION_CSS = (
    "figure.illustration { text-indent: 0; margin: 1em auto; text-align: center; } "
    "figure.illustration img { max-width: 100%; }"
)

DEFAULT_EPUB_CSS = "p { text-indent: 2em; margin: 1em 0; line-height: 1.5; text-align: justify; } " + _ILLUSTRATION_CSS
"""Default body styling applied when ``dump_epub`` receives no explicit ``css``."""
