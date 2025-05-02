mod templates;
mod hash;
mod hbs_helpers;
mod bib_tools;
mod language;
mod word_split;
mod typst_tools;
mod config;
mod event;

use pyo3::prelude::*;
use pyo3_log::init;


/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init();

    config::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    bib_tools::register(python, m)?;
    language::register(python, m)?;
    word_split::register(python, m)?;
    typst_tools::register(python, m)?;
    event::register(python, m)?;
    Ok(())
}

