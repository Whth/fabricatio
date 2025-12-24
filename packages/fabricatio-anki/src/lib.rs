use pyo3::prelude::*;

mod anki;
mod file_santitize;
use fabricatio_core::logger::init_logger_auto;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]

fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    anki::register(python, m)?;
    file_santitize::register(python, m)?;
    Ok(())
}
