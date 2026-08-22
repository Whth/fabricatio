# TODO

- [x] Add VFS-based sandbox subpackage for isolated LLM file operations
    - [x] Rust crate: `VirtualFS` trait + in-memory tree (read/write/list/delete/stat) + overlay mount system (
      copy-on-write over real paths)
    - [x] Rust crate: diff snapshot & apply — `SandboxSession` tracking all mutations, producing a unified diff, and
      optionally writing changes back to real FS
    - [x] Python bindings (PyO3) for `VirtualFS`, `SandboxSession`, overlay mounts
    - [x] Tests — Rust unit tests for VFS ops + overlay + diff/apply; Python binding smoke tests
