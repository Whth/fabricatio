use crate::config::Config;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};

use bincode::{Decode, Encode};
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::OnceLock;
use strum::{Display, EnumString, IntoStaticStr};

#[pyclass]
#[derive(Clone)]
struct Event {
    #[pyo3(get)]
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
        event.segments.push("*".to_string());
        event.segments.push(TaskStatus::Pending.to_string());
        Ok(event)
    }

    fn derive(&self, event: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut new_event = self.clone();
        let sub = Event::instantiate_from(event)?;
        new_event.segments.extend(sub.segments);
        Ok(new_event)
    }

    fn collapse(&self) -> String {
        self.segments.join(DELIMITER.get().expect("Delimiter not set!"))
    }

    fn fork(&self) -> Self {
        self.clone()
    }

    fn push<'py>(mut slf: PyRefMut<'py, Self>, segment: Bound<'py, PyAny>) -> PyResult<PyRefMut<'py, Self>> {
        if let Ok(status) = segment.extract::<TaskStatus>() {
            slf.segments.push(status.to_string());
        } else if let Ok(string) = segment.extract::<String>() {
            if string.is_empty() {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "The segment must not be empty.",
                ));
            }
            let delimiter = DELIMITER.get().expect("Delimiter not set!");
            if string.contains(delimiter) {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("The segment must not contain the delimiter '{}'", delimiter),
                ));
            }
            slf.segments.push(string);
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "The segment must be a string or TaskStatus".to_string(),
            ));
        }
        Ok(slf)
    }

    fn push_wildcard<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push("*".to_string());
        slf
    }

    fn push_pending<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Pending.to_string());
        slf
    }

    fn push_running<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Running.to_string());
        slf
    }

    fn push_finished<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Finished.to_string());
        slf
    }

    fn push_failed<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Failed.to_string());
        slf
    }

    fn push_cancelled<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Cancelled.to_string());
        slf
    }

    fn pop(&mut self) -> Option<String> {
        self.segments.pop()
    }

    fn clear(mut slf: PyRefMut<Self>) -> PyRefMut<Self> {
        slf.segments.clear();
        slf
    }


    fn concat<'py>(mut slf: PyRefMut<'py, Self>, event: &Bound<'_, PyAny>) -> PyResult<PyRefMut<'py, Self>> {
        let other = Self::instantiate_from(event)?;
        slf.segments.extend(other.segments);
        Ok(slf)
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
    Decode,
    Encode
)]
#[pyclass]
pub enum TaskStatus {
    Pending,
    Running,
    Finished,
    Failed,
    Cancelled,
}

#[pymethods]
impl TaskStatus {
    // Pickling support
    #[new]
    fn new_py(variant: u8) -> PyResult<TaskStatus> {
        match variant {
            0_u8 => Ok(TaskStatus::Pending),
            1_u8 => Ok(TaskStatus::Running),
            2_u8 => Ok(TaskStatus::Finished),
            3_u8 => Ok(TaskStatus::Failed),
            4_u8 => Ok(TaskStatus::Cancelled),
            _ => Err(pyo3::exceptions::PyValueError::new_err("Invalid variant for TaskStatus pickle"))
        }
    }
    fn __str__(&self) -> String {
        self.to_string()
    }

    fn __setstate__(&mut self, state: Bound<'_, PyBytes>) -> PyResult<()> {
        (*self, _) = bincode::decode_from_slice(state.as_bytes(), bincode::config::standard())
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Failed to deserialize TaskStatus"))?;
        Ok(())
    }


    fn __getstate__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let bytes = bincode::encode_to_vec(&self, bincode::config::standard())
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Failed to serialize TaskStatus"))?;
        Ok(PyBytes::new(py, &bytes))
    }


    fn __getnewargs__(&self) -> PyResult<(u8,)> {
        match self {
            TaskStatus::Pending => Ok((0_u8,)),
            TaskStatus::Running => Ok((1_u8,)),
            TaskStatus::Finished => Ok((2_u8,)),
            TaskStatus::Failed => Ok((3_u8,)),
            TaskStatus::Cancelled => Ok((4_u8,)),
        }
    }
}


/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    let conf = m.getattr("CONFIG")?.extract::<Config>()?;
    DELIMITER.set(conf.pymitter.delimiter).expect("Failed to set delimiter!");
    m.add_class::<TaskStatus>()?;
    m.add_class::<Event>()?;
    Ok(())
}