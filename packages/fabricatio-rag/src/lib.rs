mod tei;
mod tei_client;

use fabricatio_logger::init_logger_auto;
use pyo3::prelude::*;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]

fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    tei_client::register(python, m)?;

    Ok(())
}
