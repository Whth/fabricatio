# Stubgen Analysis Report

## Packages Handled by Stubgen (15 total)

All gated by features in `crates/fabricatio-stubgen/Cargo.toml`:

| # | Package | Feature | stubgen feature in pkg |
|---|---------|---------|----------------------|
| 1 | fabricatio-core | `core` | `["fabricatio-logger/stubgen", "fabricatio-config/stubgen"]` |
| 2 | fabricatio-memory | `memory` | `["dep:pyo3-stub-gen"]` |
| 3 | fabricatio-diff | `diff` | `[]` (pyo3-stub-gen is non-optional dep) |
| 4 | fabricatio-checkpoint | `checkpoint` | `[]` (pyo3-stub-gen is non-optional dep) |
| 5 | fabricatio-rag | `rag` | `[]` (pyo3-stub-gen is non-optional dep) |
| 6 | fabricatio-workspace | `workspace` | `["dep:pyo3-stub-gen"]` |
| 7 | fabricatio-agent | `agent` | `["dep:pyo3-stub-gen"]` |
| 8 | fabricatio-locale | `locale` | `["dep:pyo3-stub-gen"]` |
| 9 | fabricatio-thinking | `thinking` | `["dep:pyo3-stub-gen"]` |
| 10 | fabricatio-novel | `novel` | `["dep:pyo3-stub-gen"]` |
| 11 | fabricatio-anki | `anki` | `["dep:pyo3-stub-gen"]` |
| 12 | fabricatio-tool | `tool` | `["dep:pyo3-stub-gen"]` |
| 13 | fabricatio-typst | `typst` | `["dep:pyo3-stub-gen"]` |
| 14 | fabricatio-webui | `webui` | `["dep:pyo3-stub-gen"]` |
| 15 | fabricatio-tei | `tei` | `["dep:pyo3-stub-gen"]` |

## Packages NOT in Stubgen but with PyO3

**None.** All 15 packages with PyO3 bindings are covered by stubgen.

## Python Package Stub File Status

### Category 1: Correct (auto-generated `rust/__init__.pyi`, no stale `rust.pyi`)
- `fabricatio-core` — `python/fabricatio_core/rust/__init__.pyi`
- `fabricatio-memory` — `python/fabricatio_memory/rust/__init__.pyi`
- `fabricatio-rag` — `python/fabricatio_rag/rust/__init__.pyi`
- `fabricatio-typst` — `python/fabricatio_typst/rust/__init__.pyi`

### Category 2: Both old `rust.pyi` AND new `rust/__init__.pyi` (stale `rust.pyi` should be deleted)
- **`fabricatio-tei`** — `rust.pyi` is placeholder docstring; `rust/__init__.pyi` is auto-generated
- **`fabricatio-workspace`** — `rust.pyi` is placeholder docstring; `rust/__init__.pyi` is auto-generated

### Category 3: Only `rust.pyi` (missing `rust/__init__.pyi` — stale manual stubs)
- **`fabricatio-checkpoint`** — auto-generated content by pyo3_stub_gen but in old file location
- **`fabricatio-diff`** — manually written stubs (rate, match_lines, show_diff)
- **`fabricatio-webui`** — manually written stubs (start_service)
- **`fabricatio-tool`** — manually written stubs (treeview, CheckConfig, gather_violations, ToolMetaData, MCPManager)
- **`fabricatio-agent`** — placeholder docstring only (no actual stubs)
- **`fabricatio-novel`** — manually written stubs (NovelBuilder, text_to_xhtml_paragraphs)
- **`fabricatio-thinking`** — manually written stubs (ThoughtVCS)
- **`fabricatio-locale`** — manually written stubs (Msg, read_pofile, update_pofile)
- **`fabricatio-anki`** — manually written stubs (compile_deck, create_deck_project, etc.)

## Summary
- **4 packages** correctly have auto-generated `rust/__init__.pyi`
- **2 packages** need stale `rust.pyi` deleted (already have correct `rust/__init__.pyi`)
- **9 packages** need stubgen regeneration to replace manual/stale `rust.pyi` with `rust/__init__.pyi`
- **0 packages** with PyO3 are missing from stubgen
