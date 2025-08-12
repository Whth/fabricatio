use pyo3::prelude::*;
use pyo3::types::PyList;
use tracing::{debug, error, info, trace, warn};

// 使用 once_cell 定义字段键

pub const PY_SOURCE_KEY: &str = "py_source";

#[pyclass]
pub struct Logger;

impl Logger {
    #[inline]
    fn extract_py_source(inspect: &Bound<PyModule>, frames: &Bound<PyList>) -> String {
        let mut module_paths: Vec<String> = Vec::new();

        let mut iter = frames.iter().skip(1).rev();
        module_paths.push(
            iter.next()
                .expect("Failed to get frame info")
                .get_item(3)
                .unwrap()
                .extract()
                .unwrap_or("<Unknown>".to_string()),
        );
        iter.for_each(|frame_info| {
            let frame = frame_info.get_item(0).expect("Failed to get frame"); // frame object
            let module = inspect
                .call_method1("getmodule", (frame,))
                .expect("Failed to get module");
            let module_name = module
                .getattr("__name__")
                .expect("Failed to get module name")
                .extract::<String>()
                .expect("Failed to extract module name");
            module_paths.push(module_name);
        });
        module_paths.join(".")
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
    fn info(&self, msg: String) {
        Python::with_gil(|py| {
            if let Ok(inspect) = py.import("inspect")
                && let Some(frames) = Self::acquire_frames(&inspect)
            {
                let source = Self::extract_py_source(&inspect, &frames);
                info!(py_source = source, "{}", msg);
            }
        });
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
