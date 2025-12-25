//! # Fabricatio Stubgen
//!
//! A specialized Python stub generation tool for the Fabricatio ecosystem, automatically generating `.pyi` type stub files for Rust packages using PyO3 bindings.
//!
//! ## Features
//!
//! - **Automated Stub Generation**: Automatically scans and generates type stubs for fabricatio packages
//! - **PyO3 Integration**: Leverages pyo3-stub-gen for comprehensive type information
//! - **Cross-Package Support**: Handles multiple fabricatio packages (core, memory, diff)
//! - **IDE Enhancement**: Provides autocompletion and type checking for Python code
//!
//! ## Usage
//!
//! ```bash
//! # Generate stubs for all fabricatio packages
//! cargo run --bin fabricatio-stubgen
//! ```
//!
//! This generates `.pyi` files in the Python package directories that provide:
//! - Full autocompletion in IDEs
//! - Static type checking support
//! - Parameter and return type information
//!
//! ## Generated Stubs
//!
//! The tool generates type stubs for:
//! - `fabricatio-core`: Core functionality and base types
//! - `fabricatio-memory`: Memory management and data structures
//! - `fabricatio-diff`: Diff operations and comparison utilities
//!
//! For more information, see the [README](https://github.com/Whth/fabricatio/blob/main/crates/fabricatio-stubgen/README.md).

use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    fabricatio_core::stub_info()?.generate()?;
    fabricatio_memory::stub_info()?.generate()?;
    fabricatio_diff::stub_info()?.generate()?;
    Ok(())
}
