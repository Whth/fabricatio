use pyo3::prelude::*;

mod inspect;
mod linter;
mod mcp;
mod tool;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    fabricatio_logger::init_logger_auto()?;
    tool::register(python, m)?;
    mcp::register(python, m)?;
    inspect::register(python, m)?;
    Ok(())
}
