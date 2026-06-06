#![cfg_attr(feature = "stubgen", allow(dead_code, unused))]

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;

mod skill;

/// A Python module implemented in Rust.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    skill::register(python, m)?;
    Ok(())
}

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
