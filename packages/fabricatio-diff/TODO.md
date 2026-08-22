# TODO

- [x] Replace parser with native rust impl
- [x] Diff use `Hashline` impl instead of `StringGrep`
    - [x] Integrate `rho-hashline` crate + hash-based line anchoring in Rust
    - [x] Add `compute_hash`, `format_hashes`, `parse_hashline_anchor`, `apply_*` functions
- [x] Add `Diff.format_with_hashes()` method + Python exports + 22 tests
- [x] Add high-level `HashlineDiff` wrapper for hashline API
    - [x] `Diff` dataclass with anchor and line-number fields
    - [x] `from_anchors()` and `from_line_range()` factory methods
    - [x] `apply()` with line_range and pattern matching modes + tests
