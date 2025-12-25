#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

mod bib_tools;
mod typst_tools;

use fabricatio_logger::init_logger_auto;
use pyo3::prelude::*;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]

fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    bib_tools::register(python, m)?;
    typst_tools::register(python, m)?;
    Ok(())
}
