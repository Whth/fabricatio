use blake3::hash;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// calculate hash with blake3 as backbone

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pyfunction]
#[pyo3(signature=(content))]
fn blake3_hash(#[gen_stub(override_type(type_repr = "bytes"))] content: &[u8]) -> String {
    hash(content).to_string()
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(blake3_hash, m)?)?;
    Ok(())
}
