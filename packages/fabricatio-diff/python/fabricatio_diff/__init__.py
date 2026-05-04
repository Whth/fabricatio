"""An extension of fabricatio, which brings up the diff edit capabilities."""

# Hashline functions
from fabricatio_diff.rust import (
    apply_insert_after,
    apply_replace,
    apply_replace_lines,
    apply_set_line,
    compute_hash,
    format_hashes,
    parse_hashline_anchor,
)

__all__ = [
    "apply_insert_after",
    "apply_replace",
    "apply_replace_lines",
    "apply_set_line",
    "compute_hash",
    "format_hashes",
    "parse_hashline_anchor",
]
