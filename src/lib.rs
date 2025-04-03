mod templates;
mod hash;
mod hbs_helpers;
mod bib_tools;
mod language;
mod word_split;

use pyo3::prelude::*;


/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn _rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Add the TemplateManager class to the Python module
    templates::register(python, m)?;
    hash::register(python, m)?;
    bib_tools::register(python, m)?;
    language::register(python, m)?;
    word_split::register(python, m)?;
    Ok(())
}



