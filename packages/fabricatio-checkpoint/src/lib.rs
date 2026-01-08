#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

use pyo3::prelude::*;

mod checkpoint;
mod constants;
mod service;
mod store;
mod utils;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    fabricatio_logger::init_logger_auto()?;
    checkpoint::register(python, m)?;
    Ok(())
}
