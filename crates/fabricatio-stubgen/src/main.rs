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
//!
//! For more information, see the [README](https://github.com/Whth/fabricatio/blob/main/crates/fabricatio-stubgen/README.md).
use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    #[cfg(feature = "core")]
    fabricatio_core::stub_info()?.generate()?;

    #[cfg(feature = "memory")]
    fabricatio_memory::stub_info()?.generate()?;

    #[cfg(feature = "diff")]
    fabricatio_diff::stub_info()?.generate()?;

    #[cfg(feature = "checkpoint")]
    fabricatio_checkpoint::stub_info()?.generate()?;

    #[cfg(feature = "rag")]
    fabricatio_rag::stub_info()?.generate()?;

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

    Ok(())
}
