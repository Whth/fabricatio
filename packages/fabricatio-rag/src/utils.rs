use error_mapping::AsPyErr;
use pyo3::types::PyDict;
use pyo3::{Bound, PyResult, Python};
use serde_json::Value;

/// Wraps elements of a sequence in Some values.
///
/// Args:
///     seq: A vector of type T.
///
/// Returns:
///     A vector of optional values, each Some(T).
#[inline]
pub(crate) fn wraped<T>(seq: Vec<T>) -> Vec<Option<T>> {
    seq.into_iter().map(Some).collect()
}

/// Converts a JSON string to a Python dictionary.
///
/// Args:
///     python: The Python interpreter instance.
///     v: A JSON string to parse.
///
/// Returns:
///     A PyDict representation of the parsed JSON.
pub(crate) fn to_dict<S: AsRef<str>>(python: Python, v: S) -> PyResult<Bound<PyDict>> {
    pythonize::pythonize(
        python,
        &serde_json::from_str::<Value>(v.as_ref()).into_pyresult()?,
    )
    .into_pyresult()?
    .cast_into_exact::<PyDict>()
    .into_pyresult()
}
