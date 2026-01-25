use crate::constants::{CONTENT_FIELD_NAME, ID_FIELD_NAME, METADATA_FIELD_NAME, TIMESTAMP_FIELD_NAME, VECTOR_FIELD_NAME};
use crate::utils::wraped;
use arrow_array::array::*;
use arrow_array::cast::AsArray;
use arrow_array::types::*;

use arrow_array::{RecordBatch, RecordBatchIterator};
use error_mapping::AsPyErr;
use futures_util::TryStreamExt;
use lancedb::arrow::arrow_schema::*;
use lancedb::query::{ExecutableQuery, QueryBase, Select};
use lancedb::Table;
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
    /// 从 RecordBatch 行创建 SearchedDocument
    fn from_record_batch_row(
        batch: &RecordBatch,
        row_idx: usize,
    ) -> PyResult<Self> {
        let id_array = batch
            .column_by_name(ID_FIELD_NAME).map(|col| col.as_string::<i32>())
            .ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Missing or invalid {} column", ID_FIELD_NAME),
                )
            })?;
        let id = id_array.value(row_idx).to_string();

        let vector_array = batch
            .column_by_name(VECTOR_FIELD_NAME)
            .and_then(|col| col.as_fixed_size_list_opt())
            .ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Missing or invalid {} column", VECTOR_FIELD_NAME),
                )
            })?;
        let vector_values = vector_array.value(row_idx);
        let float_array = vector_values
            .as_primitive_opt::<arrow::datatypes::Float32Type>()
            .ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Vector column is not Float32 type",
                )
            })?;
        let vector: Vec<f32> = float_array.values().iter().copied().collect();

        let content_array = batch
            .column_by_name(CONTENT_FIELD_NAME).map(|col| col.as_string::<i32>())
            .ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Missing or invalid {} column", CONTENT_FIELD_NAME),
                )
            })?;
        let content = content_array.value(row_idx).to_string();


        let metadata = if let Some(col) = batch.column_by_name(METADATA_FIELD_NAME) {
            if col.is_null(row_idx) {
                None
            } else { col.as_string_opt::<i32>().map(|str_arr| str_arr.value(row_idx).to_string()) }
        } else {
            None
        };

        Ok(Self {
            id,
            content,
            vector,
            metadata,
        })
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl Document {
    fn access_metadata<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyDict>> {
        match self.metadata.clone() {
            None => Ok(PyDict::new(python)),
            Some(v) => {
                pythonize(
                    python,
                    &serde_json::from_str::<Value>(v.as_str()).into_pyresult()?,
                )
                    .into_pyresult()?
                    .cast_into_exact::<PyDict>()
                    .into_pyresult()
            }
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
                let doc = document
                    .extract::<Document>()?;
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


        future_into_py(
            python,
            async move {
                let a = table.query()
                    .nearest_to(embedding)
                    .into_pyresult()?
                    .limit(limit)
                    .select(Select::Columns(
                        vec![ID_FIELD_NAME.to_string(),
                             TIMESTAMP_FIELD_NAME.to_string(),
                             CONTENT_FIELD_NAME.to_string(),
                             METADATA_FIELD_NAME.to_string()
                        ]
                    ))
                    .execute().await
                    .into_pyresult()?
                    .try_collect::<Vec<RecordBatch>>()
                    .await
                    .into_pyresult()?;


                let mut results = Vec::new();
                for batch in a {
                    for i in 0..batch.num_rows() {
                        results.push(
                            SearchedDocument::from_record_batch_row(&batch, i)?
                        );
                    }
                }

                Ok(results)
            },
        )
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreTable>()?;
    m.add_class::<Document>()?;
    Ok(())
}
