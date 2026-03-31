#![cfg_attr(feature = "stubgen", allow(dead_code, unused, ))]

use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

mod workspace;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    workspace::register(python, m)?;
    Ok(())
}
define_stub_info_gatherer!(stub_info);
