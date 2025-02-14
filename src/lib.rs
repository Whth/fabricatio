mod downloaders;
mod templates;
use pyo3::prelude::*;


/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "_rust")]
fn _rust(_m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}

