#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

mod checkpoint;
mod constants;
mod service;
mod store;
mod utils;

define_stub_info_gatherer!(stub_info);

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    fabricatio_logger::init_logger_auto()?;
    checkpoint::register(python, m)?;
    utils::register(python, m)?;
    Ok(())
}
