use blake3::hash;
use pyo3::prelude::*;


/// calculate hash with blake3 as backbone
#[pyfunction]
#[pyo3(signature=(content))]
fn blake3_hash(content:&[u8]) ->String{
    hash(content).to_string()
}


/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(blake3_hash,m)?)?;
    Ok(())
}