use lancedb::Table;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

#[gen_stub_pyclass]
#[pyclass]
pub struct LancedbTable {
    source: Table,
}
#[gen_stub_pymethods]
#[pymethods]
impl LancedbTable {}
