mod constants;
mod memory;
mod traits;

use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.

#[cfg(not(feature = "stubgen"))]
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    memory::register(python, m)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
