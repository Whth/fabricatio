//! # Fabricatio Logger
//!
//! A comprehensive logging crate for the Fabricatio ecosystem, featuring loguru-inspired structured logging with rich ANSI color output and seamless Python/Rust interoperability through PyO3 bindings.
//!
//! ## Features
//!
//! - **Loguru-Style Formatting**: Rich ANSI color output with module/line context tracking
//! - **Python/Rust Integration**: Automatic configuration from Python settings with PyO3 bindings
//! - **Advanced Configuration**: Log rotation, thread-safe initialization, and customizable output destinations
//! - **Structured Logging**: Key-value logging via tracing subsystem with custom formatting
//!
//! ## Usage
//!
//! ```rust
//! use fabricatio_logger::{init_logger, init_logger_auto, info, debug, warn, error};
//!
//! // Manual initialization
//! init_logger("debug", None, None);
//!
//! // Or automatic configuration from Python
//! init_logger_auto().expect("Failed to initialize logger from Python config");
//!
//! // Use the logging macros
//! info!("Application started successfully");
//! debug!("Debug information: {:?}", some_data);
//! warn!("Warning: something might be wrong");
//! error!("Error occurred: {}", error_message);
//! ```
//!
//! For more information, see the [README](https://github.com/Whth/fabricatio/blob/main/crates/fabricatio-logger/README.md).

mod initializer;
mod renderer;

pub use initializer::*;
use pyo3::prelude::*;
use pyo3::types::PyList;
use pyo3_stub_gen::derive::*;
pub use tracing::{debug, error, info, trace, warn};

#[derive(Default)]
#[gen_stub_pyclass]
#[pyclass]
pub struct Logger;

impl Logger {
    #[inline]
    fn extract_py_source(inspect: &Bound<PyModule>) -> PyResult<String> {
        let stack = inspect
            .call_method1("stack", (0,))?
            .extract::<Bound<PyList>>()?;

        for frame_info in stack.iter() {
            if let Ok(frame) = frame_info.getattr("frame")
                && let Ok(m) = inspect.call_method1("getmodule", (&frame,))
                && let Ok(m) = m.cast::<PyModule>()
                && let Ok(m_name) = m.name()
                && !m_name.to_string().starts_with("asyncio.")
            {
                let func_name: String = frame_info.getattr("function")?.extract()?;
                return Ok(format!("{}:{}", m_name, func_name));
            }
        }
        Ok("<Unknown>".to_string())
    }
}
#[gen_stub_pymethods]
#[pymethods]
impl Logger {
    fn info(&self, msg: &str) -> PyResult<()> {
        Python::attach(|py| {
            let source = Self::extract_py_source(&py.import("inspect")?)?;
            info!(py_source = source, "{}", msg);
            Ok(())
        })
    }

    fn debug(&self, msg: &str) -> PyResult<()> {
        Python::attach(|py| {
            let source = Self::extract_py_source(&py.import("inspect")?)?;
            debug!(py_source = source, "{}", msg);
            Ok(())
        })
    }

    fn error(&self, msg: &str) -> PyResult<()> {
        Python::attach(|py| {
            let source = Self::extract_py_source(&py.import("inspect")?)?;
            error!(py_source = source, "{}", msg);
            Ok(())
        })
    }

    fn warn(&self, msg: &str) -> PyResult<()> {
        Python::attach(|py| {
            let source = Self::extract_py_source(&py.import("inspect")?)?;
            warn!(py_source = source, "{}", msg);
            Ok(())
        })
    }

    fn trace(&self, msg: &str) -> PyResult<()> {
        Python::attach(|py| {
            let source = Self::extract_py_source(&py.import("inspect")?)?;
            trace!(py_source = source, "{}", msg);
            Ok(())
        })
    }
}
