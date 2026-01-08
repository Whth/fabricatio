use cfg_if::cfg_if;
use pyo3::exceptions::*;
pub use pyo3::PyResult;

/// A trait for converting Rust results to Python results
pub trait AsPyErr<T> {
    /// Converts a Rust result to a Python result
    fn into_pyresult(self) -> PyResult<T>;
}

// Macro definition for implementing AsPyErr trait
#[macro_export]
/// Macro for implementing AsPyErr trait for different error types
macro_rules! impl_as_pyerr {
    ($error_type:ty, $py_err:ty) => {
        impl<T> $crate::AsPyErr<T> for ::core::result::Result<T, $error_type> {
            fn into_pyresult(self) -> $crate::PyResult<T> {
                self.map_err(|e| <$py_err>::new_err(e.to_string()))
            }
        }
    };
}

// Implementation of AsPyErr for various error types

cfg_if!(
    if #[cfg(feature = "std")]
    {
        impl_as_pyerr!(std::io::Error, PyOSError);
        impl_as_pyerr!(std::path::StripPrefixError, PyRuntimeError);
        impl_as_pyerr!(std::sync::PoisonError<T>, PyRuntimeError);
    }
);







cfg_if!(
    if #[cfg(feature = "git2")]{

        impl_as_pyerr!(git2::Error, PyRuntimeError);
        impl_as_pyerr!(std::sync::Arc<git2::Error>, PyRuntimeError);
    }
);


#[cfg(feature = "epub-builder")]
impl_as_pyerr!(epub_builder::Error, PyRuntimeError);

#[cfg(feature = "pythonize")]
impl_as_pyerr!(pythonize::PythonizeError, PyRuntimeError);

#[cfg(feature = "serde_json")]
impl_as_pyerr!(serde_json::Error, PyRuntimeError);

#[cfg(feature = "handlebars")]
impl_as_pyerr!(handlebars::RenderError, PyRuntimeError);

#[cfg(feature = "validator")]
impl_as_pyerr!(validator::ValidationErrors, PyValueError);

#[cfg(feature = "http")]
impl_as_pyerr!(http::uri::InvalidUri, PyConnectionError);

cfg_if!(

if #[cfg(feature = "tonic")]
{
impl_as_pyerr!(tonic::ConnectError, PyConnectionError);
impl_as_pyerr!(tonic::transport::Error, PyConnectionError);
impl_as_pyerr!(tonic::Status, PyConnectionError);
}
);

cfg_if!(

if #[cfg(feature = "biblatex")]
{
impl_as_pyerr!(biblatex::ParseError, PyValueError);
impl_as_pyerr!(biblatex::RetrievalError, PyOSError);
impl_as_pyerr!(biblatex::TypeError, PyTypeError);
}
);

cfg_if!(

if #[cfg(feature = "tantivy")]
{
impl_as_pyerr!(tantivy::TantivyError, PyOSError);
impl_as_pyerr!(std::sync::Arc<tantivy::TantivyError>, PyOSError);
impl_as_pyerr!(tantivy::query::QueryParserError, PyOSError);
impl_as_pyerr!(tantivy::directory::error::OpenDirectoryError, PyOSError);
}
);

#[cfg(feature = "mcp-manager")]
impl_as_pyerr!(mcp_manager::McpError, PyRuntimeError);
