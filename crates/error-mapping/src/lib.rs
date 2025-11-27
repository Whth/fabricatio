use pyo3::exceptions::{PyOSError, PyRuntimeError};
use pyo3::PyResult;
use std::sync::LockResult;

/// Trait for converting various error types to PyO3 results.
///
/// Provides a uniform interface for converting Git and synchronization errors
/// into Python exceptions that can be propagated across the FFI boundary.
pub trait AsPyErr<T> {
    /// Converts the implementing type into a `PyResult`.
    fn into_pyresult(self) -> PyResult<T>;
}

impl<T> AsPyErr<T> for LockResult<T> {
    /// Converts a poisoned lock error into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

impl<T> AsPyErr<T> for Result<T, std::io::Error> {
    /// Converts a `std::io::Error` into a Python `OSError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyOSError::new_err(e.to_string()))
    }
}
#[cfg(feature = "git2")]
impl<T> AsPyErr<T> for Result<T, git2::Error> {
    /// Converts a `git2::Error` into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[cfg(feature = "epub-builder")]
impl<T> AsPyErr<T> for Result<T, epub_builder::Error> {
    /// Converts an `epub_builder::Error` into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}
