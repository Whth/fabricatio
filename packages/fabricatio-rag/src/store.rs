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
use std::collections::HashMap;

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
    

    pub fn cols_containers(&self) -> PyResult<HashMap<String, Box<dyn Array>>> {
        self.schema_ref.fields.iter()
            .map(
                |field| {
                    let name = field.name();
                    let array = match field.data_type() {
                        DataType::Int64 => {}
                        DataType::Float64 => {}
                        DataType::Utf8 => {}
                        DataType::List(item_field) => {}
                        _ => {
                            return Err(
                                PyTypeError::new_err(format!("Unsupported data type: {}", field.data_type()))
                            )
                        }
                    };
                    Ok((name, Box::new(array)))
                }
            ).try_collect()
    }

    pub fn convert_to_reader(&self, documents: Bound<PyList>) -> PyResult<SimpleRecordBatchReader<Result<RecordBatch, lancedb::Error>>> {
        for doc in documents.into_iter() {
            let doc_dict: Bound<PyDict> = doc.cast_into_exact()?;

            // Here we would convert the Python document dictionary into an Arrow RecordBatch
            // This requires creating arrays for each field based on the schema
            // For now, we'll create a simple implementation that needs to be fleshed out

            // In a real implementation, we'd extract values from the PyDict according to the schema
            // and construct appropriate arrow arrays. This is a placeholder.

        }

        // Convert the vector of batches into a SimpleRecordBatchReader
        // Note: This is a simplified approach - actual implementation might need more careful handling
        let reader = SimpleRecordBatchReader { schema: self.schema_ref.clone(), batches };
        Ok(reader)
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl VectorStoreTable {
    fn add_document(&self, python: Python, documents: Bound<'_, PyList>) -> PyResult<Bound<'_, PyAny>> {
        let builder = self.table.add(
            self.convert_to_reader(documents)?
        );

        future_into_py(python, async move {
            Ok(builder.execute().await.into_pyresult()?.version)
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreTable>()?;
    Ok(())
}
