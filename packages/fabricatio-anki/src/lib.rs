#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

use pyo3::prelude::*;

mod anki;
mod file_sanitize;
use fabricatio_logger::init_logger_auto;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    anki::register(python, m)?;
    file_sanitize::register(python, m)?;
    Ok(())
}

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
