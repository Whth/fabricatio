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
    fn extract_py_source(inspect: &Bound<PyModule>, frames: &Bound<PyList>) -> String {
        let mut module_paths: String = frames
            .iter()
            .rev()
            .skip(1)
            .map(|frame_info| {
                let frame = frame_info.get_item(0).expect("Failed to get frame"); // frame object
                let module = inspect
                    .call_method1("getmodule", (frame,))
                    .expect("Failed to get module");
                module
                    .getattr("__name__")
                    .expect("Failed to get module name")
                    .extract::<String>()
                    .expect("Failed to extract module name")
            })
            .collect::<Vec<String>>()
            .join(".");
        module_paths.push(':');
        module_paths.push_str(
            frames
                .iter()
                .nth(0)
                .expect("Failed to get frame info")
                .get_item(3)
                .unwrap()
                .extract()
                .unwrap_or("<Unknown>"),
        );
        module_paths
    }
    #[inline]
    fn acquire_frames<'a>(inspect: &Bound<'a, PyModule>) -> Option<Bound<'a, PyList>> {
        if let Ok(stack) = inspect.call_method0("stack")
            && let Ok(frames) = stack.extract::<Bound<PyList>>()
        {
            Some(frames)
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
                && let Some(frames) = Self::acquire_frames(&inspect)
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
                && let Some(frames) = Self::acquire_frames(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                debug!(py_source = source, "{}", msg);
            }
        });
    }

    fn error(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frames(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                error!(py_source = source, "{}", msg);
            }
        });
    }
    fn warn(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frames(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                warn!(py_source = source, "{}", msg);
            }
        });
    }
    fn trace(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frames(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                trace!(py_source = source, "{}", msg);
            }
        });
    }
}
