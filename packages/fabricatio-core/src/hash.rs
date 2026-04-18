use blake3::hash;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// Calculates a BLAKE3 hash of the given content.
///
/// Args:
///     content: The byte content to hash.
///
/// Returns:
///     A hexadecimal string representation of the BLAKE3 hash.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pyfunction]
#[pyo3(signature=(content))]
fn blake3_hash(#[gen_stub(override_type(type_repr = "bytes"))] content: &[u8]) -> String {
    hash(content).to_string()
}

/// Registers the blake3_hash function with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(blake3_hash, m)?)?;
    Ok(())
}
