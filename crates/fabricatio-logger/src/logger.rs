use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyList;
use tracing::{debug, error, info, trace, warn};

pub const PY_SOURCE_KEY: &str = "py_source";

#[derive(Default)]
#[pyclass]
pub struct Logger;

impl Logger {
    #[inline]
    fn extract_py_source(inspect: &Bound<PyModule>) -> PyResult<String> {
        let stack_obj = inspect.call_method1("stack", (0,))?;
        let stack = stack_obj.extract::<Bound<PyList>>()?;

        for frame_info in stack.iter() {
            if let Ok(frame) = frame_info.getattr("frame")
                && let Ok(m) = inspect.call_method1("getmodule", (&frame,))
                && let Ok(m) = m.downcast::<PyModule>()
                && let Ok(m_name) = m.name()
                && !m_name.to_string().starts_with("asyncio.")
            {
                let func = frame_info.getattr("function")?;
                let func_name: String = func.extract()?;
                return Ok(format!("{}:{}", m_name, func_name));
            }
        }
        Ok("<Unknown>".to_string())
    }
}

#[pymethods]
impl Logger {
    fn info(&self, msg: String) -> PyResult<()> {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect") {
                let source = Self::extract_py_source(&inspect)?;
                info!(py_source = source, "{}", msg);
                Ok(())
            } else {
                Err(PyRuntimeError::new_err(
                    "Failed to import and use inspect module to extract frames.",
                ))
            }
        })
    }

    fn debug(&self, msg: String) -> PyResult<()> {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect") {
                let source = Self::extract_py_source(&inspect)?;
                debug!(py_source = source, "{}", msg);
                Ok(())
            } else {
                Err(PyRuntimeError::new_err(
                    "Failed to import and use inspect module to extract frames.",
                ))
            }
        })
    }

    fn error(&self, msg: String) -> PyResult<()> {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect") {
                let source = Self::extract_py_source(&inspect)?;
                error!(py_source = source, "{}", msg);
                Ok(())
            } else {
                Err(PyRuntimeError::new_err(
                    "Failed to import and use inspect module to extract frames.",
                ))
            }
        })
    }

    fn warn(&self, msg: String) -> PyResult<()> {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect") {
                let source = Self::extract_py_source(&inspect)?;
                warn!(py_source = source, "{}", msg);
                Ok(())
            } else {
                Err(PyRuntimeError::new_err(
                    "Failed to import and use inspect module to extract frames.",
                ))
            }
        })
    }

    fn trace(&self, msg: String) -> PyResult<()> {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect") {
                let source = Self::extract_py_source(&inspect)?;
                trace!(py_source = source, "{}", msg);
                Ok(())
            } else {
                Err(PyRuntimeError::new_err(
                    "Failed to import and use inspect module to extract frames.",
                ))
            }
        })
    }
}
