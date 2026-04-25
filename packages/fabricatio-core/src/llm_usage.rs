use pyo3::prelude::*;


#[pyclass]
struct LLMUsage {}


#[pymethods]
impl LLMUsage {
    pub fn ask<'a>(&self) -> PyResult<Bound<'a, PyAny>> {
        todo!()
    }
}
