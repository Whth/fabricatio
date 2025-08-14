use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use tracing::{debug, error, info, trace, warn};

pub const PY_SOURCE_KEY: &str = "py_source";

#[derive(Default)]
#[pyclass]
pub struct Logger;

impl Logger {
    #[inline]
    fn extract_py_source(
        inspect: &Bound<PyModule>,
        frame: &Bound<PyAny>,
    ) -> String {
        let mut module_paths: String =inspect
            .call_method1("getmodule", (frame,))
            .expect("Failed to get module")
            .getattr("__name__")
            .expect("Failed to get module name")
            .extract::<String>()
            .expect("Failed to extract module name");
        module_paths.push(':');

        module_paths.push_str(
            inspect
                .call_method1("getframeinfo", (frame,))
                .expect("Failed to get frame info")
                .getattr("function")
                .unwrap()
                .extract()
                .unwrap_or("<module>"),
        );
        module_paths
    }
    #[inline]
    fn acquire_frame<'a>(
        inspect: &Bound<'a, PyModule>,
    ) -> Option<Bound<'a, PyAny>> {
        if let Ok(frame) = inspect.call_method0("currentframe")
            && let Ok(back_frame) = frame.getattr("f_back")
        {
            Some(back_frame)
        } else {
            None
        }
    }
}

#[pymethods]
impl Logger {
    fn info(&self, msg: String) -> PyResult<()> {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frame(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                info!(py_source = source, "{}", msg);
                Ok(())
            } else {
                Err(PyRuntimeError::new_err(
                    "Failed to import and use inspect module to extract frames.",
                ))
            }
        })
    }

    fn debug(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frame(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                debug!(py_source = source, "{}", msg);
            }
        });
    }

    fn error(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frame(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                error!(py_source = source, "{}", msg);
            }
        });
    }
    fn warn(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frame(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                warn!(py_source = source, "{}", msg);
            }
        });
    }
    fn trace(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frame(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                trace!(py_source = source, "{}", msg);
            }
        });
    }
}
