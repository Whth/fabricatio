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

/// Computes the cosine similarity between two equal-length slices.
///
/// Returns `0.0` when either input has zero norm, since its direction is undefined.
#[inline]
pub(crate) fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let mut dot = 0.0_f32;
    let mut norm_a = 0.0_f32;
    let mut norm_b = 0.0_f32;

    for (&x, &y) in a.iter().zip(b.iter()) {
        dot += x * y;
        norm_a += x * x;
        norm_b += y * y;
    }

    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }

    dot / (norm_a.sqrt() * norm_b.sqrt())
}
