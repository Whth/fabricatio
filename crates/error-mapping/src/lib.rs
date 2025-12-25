use cfg_if::cfg_if;
pub use pyo3::PyResult;
use pyo3::exceptions::*;

/// Trait for converting various error types to PyO3 results.
///
/// Provides a uniform interface for converting Git and synchronization errors
/// into Python exceptions that can be propagated across the FFI boundary.
pub trait AsPyErr<T> {
    /// Converts the implementing type into a `PyResult`.
    fn into_pyresult(self) -> PyResult<T>;
}

#[cfg(feature = "std")]
impl<T> AsPyErr<T> for std::sync::LockResult<T> {
    /// Converts a poisoned lock error into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[cfg(feature = "std")]
impl<T> AsPyErr<T> for std::io::Result<T> {
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
impl<T> AsPyErr<T> for epub_builder::Result<T> {
    /// Converts an `epub_builder::Error` into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[cfg(feature = "pythonize")]
impl<T> AsPyErr<T> for pythonize::Result<T> {
    /// Converts a `pythonize::Error` into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[cfg(feature = "serde_json")]
impl<T> AsPyErr<T> for serde_json::Result<T> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[cfg(feature = "handlebars")]
impl<T> AsPyErr<T> for Result<T, handlebars::RenderError> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

cfg_if!(if #[cfg(feature = "biblatex")] {

impl <T> AsPyErr<T> for Result<T, biblatex::ParseError> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

impl <T> AsPyErr<T> for Result<T, biblatex::RetrievalError> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyOSError::new_err(e.to_string()))
    }
}

impl <T> AsPyErr<T> for Result<T, biblatex::TypeError> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyTypeError::new_err(e.to_string()))
    }
}

});
