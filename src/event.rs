use crate::config::Config;
use pyo3::prelude::*;
use pyo3::types::PyList;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::OnceLock;
use strum::{Display, EnumString, IntoStaticStr};

#[pyclass]
#[derive(Clone)]
struct Event {
    segments: Vec<String>,
}

static DELIMITER: OnceLock<String> = OnceLock::new();

#[pymethods]
impl Event {
    #[new]
    #[pyo3(signature = (segments=None))]
    fn new(segments: Option<Vec<String>>) -> Self {
        Event {
            segments: segments.unwrap_or_default(),
        }
    }

    #[staticmethod]
    fn instantiate_from(event: &Bound<'_, PyAny>) -> PyResult<Self> {
        if let Ok(event_str) = event.extract::<String>() {
            let delimiter = DELIMITER.get().expect("Delimiter not set!");
            let segments: Vec<String> = event_str
                .split(delimiter)
                .map(|s| s.to_string())
                .collect();
            Ok(Event { segments })
        } else if let Ok(event_list) = event.downcast::<PyList>() {
            let mut segments = Vec::new();
            for item in event_list.iter() {
                if let Ok(s) = item.extract::<String>() {
                    segments.push(s);
                } else {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "List elements must be strings",
                    ));
                }
            }
            Ok(Event { segments })
        } else if let Ok(py_event) = event.extract::<Self>() {
            Ok(py_event.clone())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "Invalid event type",
            ))
        }
    }

    #[staticmethod]
    fn quick_instantiate(event: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut event = Self::instantiate_from(event)?;
        event.push_wildcard()?;
        event.push_pending()?;
        Ok(event)
    }

    fn derive(&self, event: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut new_event = self.clone();
        new_event.concat(event)?;
        Ok(new_event)
    }

    fn collapse(&self) -> String {
        let delimiter = DELIMITER.get().expect("Delimiter not set!");
        self.segments.join(&delimiter)
    }

    fn clone(&self) -> Self {
        Event {
            segments: self.segments.clone(),
        }
    }

    fn push(&mut self, segment: String) -> PyResult<()> {
        if segment.is_empty() {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "The segment must not be empty.",
            ));
        }
        let delimiter = DELIMITER.get().expect("Delimiter not set!");
        if segment.contains(delimiter) {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("The segment must not contain the delimiter '{}'", delimiter),
            ));
        }
        self.segments.push(segment);
        Ok(())
    }

    fn push_wildcard(&mut self) -> PyResult<()> {
        self.push("*".to_string())
    }

    fn push_pending(&mut self) -> PyResult<()> {
        self.push(TaskStatus::Pending.to_string())
    }

    fn push_running(&mut self) -> PyResult<()> {
        self.push(TaskStatus::Running.to_string())
    }

    fn push_finished(&mut self) -> PyResult<()> {
        self.push(TaskStatus::Finished.to_string())
    }

    fn push_failed(&mut self) -> PyResult<()> {
        self.push(TaskStatus::Failed.to_string())
    }

    fn push_cancelled(&mut self) -> PyResult<()> {
        self.push(TaskStatus::Cancelled.to_string())
    }

    fn pop(&mut self) -> Option<String> {
        self.segments.pop()
    }

    fn clear(&mut self) {
        self.segments.clear();
    }

    fn concat(&mut self, event: &Bound<'_, PyAny>) -> PyResult<()> {
        let other = Self::instantiate_from(event)?;
        self.segments.extend(other.segments);
        Ok(())
    }

    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.collapse().hash(&mut hasher);
        hasher.finish()
    }

    fn __richcmp__(&self, other: &Bound<'_, PyAny>, op: pyo3::class::basic::CompareOp) -> PyResult<bool> {
        if let Ok(_other_str) = other.extract::<String>() {
            let other_event = Self::instantiate_from(other)?;
            let result = self.collapse() == other_event.collapse();
            Ok(match op {
                pyo3::class::basic::CompareOp::Eq => result,
                pyo3::class::basic::CompareOp::Ne => !result,
                _ => unimplemented!(),
            })
        } else if let Ok(other_event) = other.extract::<Self>() {
            let result = self.collapse() == other_event.collapse();
            Ok(match op {
                pyo3::class::basic::CompareOp::Eq => result,
                pyo3::class::basic::CompareOp::Ne => !result,
                _ => unimplemented!(),
            })
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "Comparison requires string or Event instance",
            ))
        }
    }
}
#[pyclass]
#[derive(
    Clone,
    Copy,
    Debug,
    PartialEq,
    Eq,
    Hash,
    Display,
    EnumString,
    IntoStaticStr,
    Serialize,
    Deserialize,
)]
pub enum TaskStatus {
    Pending,
    Running,
    Finished,
    Failed,
    Cancelled,
}


/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    let conf = m.getattr("CONFIG")?.extract::<Config>()?;
    DELIMITER.set(conf.pymitter.delimiter).expect("Failed to set delimiter!");
    m.add_class::<TaskStatus>()?;
    m.add_class::<Event>()?;
    Ok(())
}