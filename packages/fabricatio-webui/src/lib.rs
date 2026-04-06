#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

use pyo3::prelude::*;

use fabricatio_logger::init_logger_auto;
mod webui;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    webui::register(python, m)?;
    Ok(())
}

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
