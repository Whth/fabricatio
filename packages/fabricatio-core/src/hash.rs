use blake3::hash;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// calculate hash with blake3 as backbone

#[gen_stub_pyfunction]
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
