use crate::constants::{
    CONTENT_FIELD_NAME, ID_FIELD_NAME, METADATA_FIELD_NAME, TIMESTAMP_FIELD_NAME, VECTOR_FIELD_NAME,
};
use crate::utils::wraped;
use arrow_array::array::*;
use arrow_array::cast::AsArray;
use arrow_array::types::*;

use arrow_array::{RecordBatch, RecordBatchIterator};
use error_mapping::AsPyErr;
use futures_util::TryStreamExt;
use lancedb::Table;
use lancedb::arrow::arrow_schema::*;
use lancedb::query::{ExecutableQuery, QueryBase, Select};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use rayon::prelude::*;
use serde_json::Value;
use std::iter::repeat_n;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

type JsonString = String;

type Dim = f32;

type Vector = Vec<Dim>;

type WrappedVector = Vec<Option<Dim>>;
type ContentText = String;

type UuidString = String;

type TimeStamp = i64;

type DataContainers = (
    Vec<UuidString>,
    Vec<TimeStamp>,
    Vec<Option<WrappedVector>>,
    Vec<ContentText>,
    Vec<Option<JsonString>>,
);

#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct Document {
    content: String,
    vector: Vector,
    metadata: Option<JsonString>,
}

#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct SearchedDocument {
    id: UuidString,
    content: String,
    vector: Vector,
    metadata: Option<JsonString>,
}

impl SearchedDocument {
    /// Build a SearchedDocument from a single row in a RecordBatch.
    fn from_record_batch_row(batch: &RecordBatch, row_idx: usize) -> PyResult<Self> {
        let id = Self::extract_string_column(batch, ID_FIELD_NAME, row_idx)?;
        let vector = Self::extract_f32_vector_column(batch, VECTOR_FIELD_NAME, row_idx)?;
        let content = Self::extract_string_column(batch, CONTENT_FIELD_NAME, row_idx)?;
        let metadata = Self::extract_optional_string_column(batch, METADATA_FIELD_NAME, row_idx)?;

        Ok(Self {
            id,
            content,
            vector,
            metadata,
        })
    }

    // --- Helper methods ---

    #[inline]
    fn extract_string_column(
        batch: &RecordBatch,
        col_name: &str,
        row_idx: usize,
    ) -> PyResult<String> {
        let array = batch
            .column_by_name(col_name)
            .ok_or_else(|| Self::missing_column_error(col_name))?
            .as_string_opt::<i32>()
            .ok_or_else(|| Self::invalid_type_error(col_name, "string"))?;

        if array.is_null(row_idx) {
            return Err(Self::null_value_error(col_name, row_idx));
        }

        Ok(array.value(row_idx).to_string())
    }

    #[inline]
    fn extract_optional_string_column(
        batch: &RecordBatch,
        col_name: &str,
        row_idx: usize,
    ) -> PyResult<Option<String>> {
        if let Some(col) = batch.column_by_name(col_name)
            && let Some(str_arr) = col.as_string_opt::<i32>()
        {
            if str_arr.is_null(row_idx) {
                return Ok(None);
            }
            return Ok(Some(str_arr.value(row_idx).to_string()));
        }
        Ok(None)
    }

    #[inline]
    fn extract_f32_vector_column(
        batch: &RecordBatch,
        col_name: &str,
        row_idx: usize,
    ) -> PyResult<Vec<f32>> {
        let list_array = batch
            .column_by_name(col_name)
            .ok_or_else(|| Self::missing_column_error(col_name))?
            .as_fixed_size_list_opt()
            .ok_or_else(|| Self::invalid_type_error(col_name, "fixed-size list"))?;

        let values = list_array.value(row_idx);
        let float_array = values
            .as_primitive_opt::<Float32Type>()
            .ok_or_else(|| Self::invalid_vector_type_error(col_name))?;

        Ok(float_array.values().iter().copied().collect())
    }

    // --- Error utilities (private, inline, zero-cost) ---

    #[inline]
    fn missing_column_error(col_name: &str) -> PyErr {
        PyValueError::new_err(format!("Column '{}' not found in table schema", col_name))
    }

    #[inline]
    fn invalid_type_error(col_name: &str, expected: &str) -> PyErr {
        PyValueError::new_err(format!(
            "Column '{}' is not of expected type: {}",
            col_name, expected
        ))
    }

    #[inline]
    fn invalid_vector_type_error(col_name: &str) -> PyErr {
        PyValueError::new_err(format!(
            "Vector column '{}' does not contain f32 values (required for embeddings)",
            col_name
        ))
    }

    #[inline]
    fn null_value_error(col_name: &str, row_idx: usize) -> PyErr {
        PyValueError::new_err(format!(
            "Non-nullable column '{}' is null at row {}",
            col_name, row_idx
        ))
    }
}
#[gen_stub_pymethods]
#[pymethods]
impl Document {
    fn access_metadata<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyDict>> {
        match self.metadata.clone() {
            None => Ok(PyDict::new(python)),
            Some(v) => pythonize(
                python,
                &serde_json::from_str::<Value>(v.as_str()).into_pyresult()?,
            )
            .into_pyresult()?
            .cast_into_exact::<PyDict>()
            .into_pyresult(),
        }
    }
}

#[gen_stub_pyclass]
#[pyclass]
pub(crate) struct VectorStoreTable {
    ndim: i32,
    table: Table,
    schema_ref: SchemaRef,
}

impl VectorStoreTable {
    pub fn new(ndim: i32, table: Table, schema_ref: SchemaRef) -> Self {
        Self {
            ndim,
            table,
            schema_ref,
        }
    }

    pub async fn open(table: Table) -> PyResult<Self> {
        let schema_ref = table.schema().await.into_pyresult()?;

        let vector_field_ref = schema_ref
            .fields
            .find(VECTOR_FIELD_NAME)
            .ok_or_else(|| PyValueError::new_err("Vector field not found in schema".to_string()))?
            .1
            .clone();

        let ndim = match vector_field_ref.data_type() {
            DataType::FixedSizeList(_, size) => *size,
            _ => {
                return Err(PyRuntimeError::new_err(
                    "Vector field is not a `FixedSizeList`".to_string(),
                ));
            }
        };

        Ok(Self {
            ndim,
            schema_ref,
            table,
        })
    }
    pub async fn add_documents_inner(
        ndim: i32,
        table: Table,
        schema_ref: SchemaRef,
        documents: Vec<Document>,
    ) -> PyResult<Vec<String>> {
        let (mut id_seq, timestamp_seq, mut vector_seq, mut content_seq, mut metadata_seq) =
            Self::make_container(documents.len())?;

        Self::inject_data(
            documents,
            &mut id_seq,
            &mut vector_seq,
            &mut content_seq,
            &mut metadata_seq,
        );

        let batch = RecordBatch::try_new(
            schema_ref.clone(),
            vec![
                Arc::new(StringArray::from(id_seq.clone())),
                Arc::new(Time64MicrosecondArray::from(timestamp_seq)),
                Arc::new(
                    FixedSizeListArray::from_iter_primitive::<Float32Type, _, _>(vector_seq, ndim),
                ),
                Arc::new(StringArray::from(content_seq)),
                Arc::new(StringArray::from(metadata_seq)),
            ],
        );

        let it = RecordBatchIterator::new(vec![batch], schema_ref);
        table.add(it).execute().await.into_pyresult()?;
        Ok(id_seq)
    }

    #[inline]
    fn inject_data(
        documents: Vec<Document>,
        id_seq: &mut Vec<String>,
        vector_seq: &mut Vec<Option<WrappedVector>>,
        content_seq: &mut Vec<String>,
        metadata_seq: &mut Vec<Option<JsonString>>,
    ) {
        documents
            .into_par_iter()
            .map(|doc| {
                (
                    Uuid::new_v4().to_string(),
                    Some(wraped(doc.vector)),
                    doc.content,
                    doc.metadata,
                )
            })
            .collect::<Vec<_>>()
            .into_iter()
            .for_each(|(id, vector, content, metadata)| {
                id_seq.push(id);
                vector_seq.push(vector);
                content_seq.push(content);
                metadata_seq.push(metadata);
            });
    }

    #[inline]
    fn make_container(length: usize) -> PyResult<DataContainers> {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .into_pyresult()?
            .as_micros() as i64;

        let id_seq: Vec<String> = vec![];
        let timestamp_seq: Vec<i64> = repeat_n(stamp, length).collect();
        let vector_seq: Vec<Option<WrappedVector>> = vec![];
        let content_seq: Vec<String> = vec![];
        let metadata_seq: Vec<Option<JsonString>> = vec![];
        Ok((id_seq, timestamp_seq, vector_seq, content_seq, metadata_seq))
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl VectorStoreTable {
    fn add_documents<'a>(
        &self,
        python: Python<'a>,
        documents: Bound<'a, PyList>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let docs = documents
            .iter()
            .map(|document| {
                let doc = document.extract::<Document>()?;
                Ok(doc)
            })
            .collect::<PyResult<Vec<Document>>>()?;

        future_into_py(
            python,
            Self::add_documents_inner(self.ndim, self.table.clone(), self.schema_ref.clone(), docs),
        )
    }

    fn search_document<'a>(
        &self,
        python: Python<'a>,
        embedding: Vector,
        limit: usize,
    ) -> PyResult<Bound<'a, PyAny>> {
        let table = self.table.clone();

        future_into_py(python, async move {
            let a = table
                .query()
                .nearest_to(embedding)
                .into_pyresult()?
                .limit(limit)
                .select(Select::Columns(vec![
                    ID_FIELD_NAME.to_string(),
                    TIMESTAMP_FIELD_NAME.to_string(),
                    CONTENT_FIELD_NAME.to_string(),
                    METADATA_FIELD_NAME.to_string(),
                ]))
                .execute()
                .await
                .into_pyresult()?
                .try_collect::<Vec<RecordBatch>>()
                .await
                .into_pyresult()?;

            let mut results = Vec::new();
            for batch in a {
                for i in 0..batch.num_rows() {
                    results.push(SearchedDocument::from_record_batch_row(&batch, i)?);
                }
            }

            Ok(results)
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreTable>()?;
    m.add_class::<Document>()?;
    Ok(())
}
