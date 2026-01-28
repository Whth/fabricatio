use error_mapping::AsPyErr;
use pyo3::types::PyDict;
use pyo3::{Bound, PyResult, Python};
use serde_json::Value;

#[inline]
pub(crate) fn wraped<T>(seq: Vec<T>) -> Vec<Option<T>> {
    seq.into_iter().map(Some).collect()
}

pub(crate) fn to_dict<S: AsRef<str>>(python: Python, v: S) -> PyResult<Bound<PyDict>> {
    pythonize::pythonize(
        python,
        &serde_json::from_str::<Value>(v.as_ref()).into_pyresult()?,
    )
    .into_pyresult()?
    .cast_into_exact::<PyDict>()
    .into_pyresult()
}
