use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};

use postcard::{from_bytes, to_stdvec};
use pyo3::exceptions::{PyTypeError, PyValueError};
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::OnceLock;
use strum::{Display, EnumString, IntoStaticStr};

use error_mapping::AsPyErr;
use pyo3_stub_gen::derive::*;

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(from_py_object)]
#[derive(Clone)]
struct Event {
    #[pyo3(get)]
    segments: Vec<String>,
}

static DELIMITER: OnceLock<String> = OnceLock::new();

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl Event {
    /// Creates a new Event instance.
    ///
    /// Args:
    ///     segments: Optional list of event segments. Defaults to empty list.
    #[new]
    #[pyo3(signature = (segments=None))]
    fn new(segments: Option<Vec<String>>) -> Self {
        Event {
            segments: segments.unwrap_or_default(),
        }
    }

    /// Creates an Event from various input types.
    ///
    /// Args:
    ///     event: A string, list of strings, or another Event instance.
    ///
    /// Returns:
    ///     A new Event instance with segments extracted from the input.
    #[staticmethod]
    fn instantiate_from(
        #[gen_stub(override_type(type_repr = "typing.List[str] | str | Event"))] event: &Bound<
            '_,
            PyAny,
        >,
    ) -> PyResult<Self> {
        if let Ok(event_str) = event.extract::<String>() {
            let delimiter = DELIMITER.get().expect("Delimiter not set!");
            let segments: Vec<String> = event_str.split(delimiter).map(|s| s.to_string()).collect();
            Ok(Event { segments })
        } else if let Ok(event_list) = event.cast::<PyList>() {
            let mut segments = Vec::new();
            for item in event_list.iter() {
                if let Ok(s) = item.extract::<String>() {
                    segments.push(s);
                } else {
                    return Err(PyValueError::new_err("List elements must be strings"));
                }
            }
            Ok(Event { segments })
        } else if let Ok(py_event) = event.extract::<Self>() {
            Ok(py_event.clone())
        } else {
            Err(PyTypeError::new_err("Invalid event type"))
        }
    }

    /// Creates an Event with wildcard and pending status appended.
    ///
    /// Args:
    ///     event: A string, list of strings, or another Event instance.
    ///
    /// Returns:
    ///     A new Event instance with "*" and "Pending" segments appended.
    #[staticmethod]
    fn quick_instantiate(
        #[gen_stub(override_type(type_repr = "typing.List[str] | str | Event"))] event: &Bound<
            '_,
            PyAny,
        >,
    ) -> PyResult<Self> {
        let mut event = Self::instantiate_from(event)?;
        event.segments.push("*".to_string());
        event.segments.push(TaskStatus::Pending.to_string());
        Ok(event)
    }

    /// Derives a new event by appending segments from another event.
    ///
    /// Args:
    ///     event: A string, list of strings, or another Event instance to append.
    ///
    /// Returns:
    ///     A new Event with the combined segments.
    fn derive(
        &self,
        #[gen_stub(override_type(type_repr = "typing.List[str] | str | Event"))] event: &Bound<
            '_,
            PyAny,
        >,
    ) -> PyResult<Self> {
        let mut new_event = self.clone();
        let sub = Event::instantiate_from(event)?;
        new_event.segments.extend(sub.segments);
        Ok(new_event)
    }

    /// Collapses the event segments into a single delimited string.
    ///
    /// Returns:
    ///     A string with segments joined by the configured delimiter.
    fn collapse(&self) -> String {
        self.segments
            .join(DELIMITER.get().expect("Delimiter not set!"))
    }

    /// Creates a copy of the event.
    ///
    /// Returns:
    ///     A clone of this Event instance.
    fn fork(&self) -> Self {
        self.clone()
    }

    /// Pushes a segment onto the event.
    ///
    /// Args:
    ///     segment: A TaskStatus enum or string to append.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push<'py>(
        mut slf: PyRefMut<'py, Self>,
        #[gen_stub(override_type(type_repr = "TaskStatus | str "))] segment: Bound<'py, PyAny>,
    ) -> PyResult<PyRefMut<'py, Self>> {
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
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "The segment must not contain the delimiter '{}'",
                    delimiter
                )));
            }
            slf.segments.push(string);
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "The segment must be a string or TaskStatus".to_string(),
            ));
        }
        Ok(slf)
    }

    /// Appends a wildcard segment to the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push_wildcard<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push("*".to_string());
        slf
    }

    /// Appends a Pending status segment to the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push_pending<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Pending.to_string());
        slf
    }

    /// Appends a Running status segment to the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push_running<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Running.to_string());
        slf
    }

    /// Appends a Finished status segment to the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push_finished<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Finished.to_string());
        slf
    }

    /// Appends a Failed status segment to the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push_failed<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Failed.to_string());
        slf
    }

    /// Appends a Cancelled status segment to the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn push_cancelled<'py>(mut slf: PyRefMut<'py, Self>) -> PyRefMut<'py, Self> {
        slf.segments.push(TaskStatus::Cancelled.to_string());
        slf
    }

    /// Removes and returns the last segment.
    ///
    /// Returns:
    ///     The last segment if present, None otherwise.
    fn pop(&mut self) -> Option<String> {
        self.segments.pop()
    }

    /// Clears all segments from the event.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance.
    fn clear(mut slf: PyRefMut<Self>) -> PyRefMut<Self> {
        slf.segments.clear();
        slf
    }

    /// Concatenates another event's segments onto this event.
    ///
    /// Args:
    ///     event: A string, list of strings, or another Event instance to append.
    ///
    /// Returns:
    ///     A mutable reference to this Event instance with combined segments.
    fn concat<'py>(
        mut slf: PyRefMut<'py, Self>,
        #[gen_stub(override_type(type_repr = "typing.List[str] | str | Event"))] event: &Bound<
            '_,
            PyAny,
        >,
    ) -> PyResult<PyRefMut<'py, Self>> {
        let other = Self::instantiate_from(event)?;
        slf.segments.extend(other.segments);
        Ok(slf)
    }

    /// Computes the hash of the collapsed event string.
    ///
    /// Returns:
    ///     The hash value as a u64.
    fn __hash__(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.collapse().hash(&mut hasher);
        hasher.finish()
    }

    /// Compares this event with another value for equality.
    ///
    /// Args:
    ///     other: Another Event instance or string to compare against.
    ///     op: The comparison operation (Eq or Ne).
    ///
    /// Returns:
    ///     True if the comparison holds, False otherwise.
    fn __richcmp__(
        &self,
        other: &Bound<'_, PyAny>,
        op: pyo3::class::basic::CompareOp,
    ) -> PyResult<bool> {
        if let Ok(other_str) = other.extract::<String>() {
            let result = self.collapse() == other_str;
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
            Err(PyTypeError::new_err(
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
)]
#[cfg_attr(feature = "stubgen", gen_stub_pyclass_enum)]
#[pyclass(from_py_object)]
pub enum TaskStatus {
    Pending,
    Running,
    Finished,
    Failed,
    Cancelled,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
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
            _ => Err(PyValueError::new_err(
                "Invalid variant for TaskStatus pickle",
            )),
        }
    }
    fn __str__(&self) -> String {
        self.to_string()
    }

    fn __setstate__(&mut self, state: Bound<'_, PyBytes>) -> PyResult<()> {
        *self = from_bytes(state.as_bytes()).into_pyresult()?;

        Ok(())
    }

    fn __getstate__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        to_stdvec(self)
            .into_pyresult()
            .map(|b| PyBytes::new(py, &b))
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

/// Registers the Event and TaskStatus classes with the Python module.
///
/// Args:
///     _: The Python interpreter instance (unused).
///     m: The Python module to register classes with.
///
/// Returns:
///     PyResult<()> indicating success or failure.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    DELIMITER
        .set(fabricatio_config::CONFIG.emitter.delimiter.clone())
        .map_err(PyValueError::new_err)?;
    m.add_class::<TaskStatus>()?;
    m.add_class::<Event>()?;
    Ok(())
}
