//! # Fabricatio Stubgen
//!
//! A specialized Python stub generation tool for the Fabricatio ecosystem, automatically generating `.pyi` type stub files for Rust packages using PyO3 bindings.
//!
//! ## Features
//!
//! - **Automated Stub Generation**: Automatically scans and generates type stubs for fabricatio packages
//! - **PyO3 Integration**: Leverages pyo3-stub-gen for comprehensive type information
//! - **Cross-Package Support**: Handles multiple fabricatio packages (core, memory, diff)
//! - **Post-generation Polish**: Runs `ruff check --fix` and `ruff format` over every emitted `.pyi` so generated stubs comply with the repo's ruff config (the generator itself emits a stale `# ruff: noqa` header and multi-line docstrings). Opt out with `--no-polish`.
//! - **IDE Enhancement**: Provides autocompletion and type checking for Python code
//!
//! ## Usage
//!
//! ```bash
//! # Generate stubs for all fabricatio packages
//! cargo run --bin fabricatio-stubgen --features all
//!
//! # Generate without the post-generation ruff polish
//! cargo run --bin fabricatio-stubgen --features all -- --no-polish
//! ```
//!
//! This generates `.pyi` files in the Python package directories that provide:
//! - Full autocompletion in IDEs
//! - Static type checking support
//! - Parameter and return type information
//!
//!
//! For more information, see the [README](https://github.com/Whth/fabricatio/blob/main/crates/fabricatio-stubgen/README.md).
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use pyo3_stub_gen::Result;

/// Collect every `<pkg>/python/<module>/rust/__init__.pyi` under `<repo>/packages`.
fn discover_stubs() -> Vec<PathBuf> {
    let Some(root) = Path::new(env!("CARGO_MANIFEST_DIR")).ancestors().nth(2).map(Path::to_path_buf) else {
        return Vec::new();
    };
    let packages_dir = root.join("packages");
    let Ok(entries) = fs::read_dir(&packages_dir) else {
        eprintln!("polish: cannot read {packages_dir:?}; skipping");
        return Vec::new();
    };
    let mut stubs = Vec::new();
    for pkg in entries.flatten() {
        let python_dir = pkg.path().join("python");
        if !python_dir.is_dir() {
            continue;
        }
        for module in fs::read_dir(&python_dir).into_iter().flatten().flatten() {
            let stub = module.path().join("rust").join("__init__.pyi");
            if stub.is_file() {
                stubs.push(stub);
            }
        }
    }
    stubs
}

/// Run one ruff subcommand over the stubs in chunks; warn (never fail) on errors.
fn run_ruff(root: &Path, args: &[&str], stubs: &[PathBuf]) {
    for chunk in stubs.chunks(64) {
        match Command::new("ruff").args(args).args(chunk).current_dir(root).status() {
            Ok(s) if s.success() => {}
            Ok(s) => eprintln!("polish: ruff {} exited with {s}", args.first().unwrap_or(&"")),
            Err(e) => eprintln!("polish: failed to launch ruff ({e}); skipping"),
        }
    }
}

/// Post-generation polish: make every emitted `.pyi` comply with the repo ruff config.
fn polish_stubs() {
    let Some(root) = Path::new(env!("CARGO_MANIFEST_DIR")).ancestors().nth(2).map(Path::to_path_buf) else {
        return;
    };
    let stubs = discover_stubs();
    if stubs.is_empty() {
        return;
    }
    // Chunk to stay under command-line length limits on Windows.
    run_ruff(&root, &["check", "--fix"], &stubs);
    run_ruff(&root, &["format"], &stubs);
}

fn main() -> Result<()> {
    let no_polish = std::env::args().any(|a| a == "--no-polish");

    #[cfg(feature = "core")]
    fabricatio_core::stub_info()?.generate()?;

    #[cfg(feature = "memory")]
    fabricatio_memory::stub_info()?.generate()?;

    #[cfg(feature = "diff")]
    fabricatio_diff::stub_info()?.generate()?;

    #[cfg(feature = "checkpoint")]
    fabricatio_checkpoint::stub_info()?.generate()?;

    #[cfg(feature = "lancedb")]
    fabricatio_lancedb::stub_info()?.generate()?;

    #[cfg(feature = "workspace")]
    fabricatio_workspace::stub_info()?.generate()?;

    #[cfg(feature = "agent")]
    fabricatio_agent::stub_info()?.generate()?;

    #[cfg(feature = "locale")]
    fabricatio_locale::stub_info()?.generate()?;

    #[cfg(feature = "thinking")]
    fabricatio_thinking::stub_info()?.generate()?;

    #[cfg(feature = "novel")]
    fabricatio_novel::stub_info()?.generate()?;

    #[cfg(feature = "sandbox")]
    fabricatio_sandbox::stub_info()?.generate()?;

    #[cfg(feature = "anki")]
    fabricatio_anki::stub_info()?.generate()?;

    #[cfg(feature = "tool")]
    fabricatio_tool::stub_info()?.generate()?;

    #[cfg(feature = "typst")]
    fabricatio_typst::stub_info()?.generate()?;

    #[cfg(feature = "webui")]
    fabricatio_webui::stub_info()?.generate()?;

    #[cfg(feature = "tei")]
    fabricatio_tei::stub_info()?.generate()?;
    #[cfg(feature = "skill")]
    fabricatio_skill::stub_info()?.generate()?;

    if !no_polish {
        polish_stubs();
    }

    println!("Stubgen Done!");
    Ok(())
}
