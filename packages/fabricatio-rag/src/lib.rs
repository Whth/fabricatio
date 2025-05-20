mod tei;
mod tei_client;

use pyo3::prelude::*;
use pyo3_log::init;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init();
    tei_client::register(python, m)?;
    Ok(())
}
