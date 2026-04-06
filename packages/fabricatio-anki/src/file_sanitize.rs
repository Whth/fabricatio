use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use sanitize_filename::sanitize;
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn fname_santitize(filename: &str) -> PyResult<String> {
    Ok(sanitize(filename))
}
/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fname_santitize, m)?)?;
    Ok(())
}
