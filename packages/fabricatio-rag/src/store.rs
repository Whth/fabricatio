use arrow::datatypes::DataType::FixedSizeList;
use arrow_array::{Array, RecordBatch, StringArray};
use error_mapping::AsPyErr;
use lancedb::arrow::arrow_schema::{DataType, SchemaRef};
use lancedb::arrow::SimpleRecordBatchReader;
use lancedb::Table;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;

#[gen_stub_pyclass]
#[pyclass]
pub(crate) struct VectorStoreTable {
    table: Table,
    schema_ref: SchemaRef,
}

impl VectorStoreTable {
    pub fn new(table: Table, schema_ref: SchemaRef) -> Self {
        Self {
            table
            ,
            schema_ref,
        }
    }

    pub async fn open(table: Table) -> PyResult<Self> {
        Ok(Self {
            schema_ref: table.schema().await.into_pyresult()?,
            table,
        })
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl VectorStoreTable {
    fn add_document(&self, python: Python, documents: Bound<'_, PyList>) -> PyResult<Bound<'_, PyAny>> {
        todo!();
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreTable>()?;
    Ok(())
}
