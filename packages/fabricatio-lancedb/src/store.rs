use crate::constants::{
    CONTENT_FIELD_NAME, ID_FIELD_NAME, METADATA_FIELD_NAME, TIMESTAMP_FIELD_NAME, VECTOR_FIELD_NAME,
};
use crate::utils::wraped;
use arrow_array::array::*;
use arrow_array::cast::AsArray;
use arrow_array::types::*;

use arrow_array::RecordBatch;
use error_mapping::AsPyErr;
use futures_util::TryStreamExt;
use lancedb::Table;
use lancedb::arrow::arrow_schema::*;
use lancedb::index::Index;
use lancedb::query::{ExecutableQuery, QueryBase, Select};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::utils;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use pythonize::depythonize;
use rayon::prelude::*;
use serde_json::Value;
use std::collections::HashSet;
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

/// Candidate oversampling factor applied when cosine deduplication is enabled: this many
/// nearest rows are fetched per requested result so filtering can still fill `limit`.
const DEDUP_OVERSAMPLE_FACTOR: usize = 4;

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(set_all, get_all, from_py_object)]
#[derive(Clone, Debug)]
pub struct StoreDocument {
    content: String,
    vector: Vector,
    metadata: Option<JsonString>,
}

/// Represents a document that has been searched and retrieved from the vector store.
///
/// This structure contains the core information of a searched document including
/// its unique identifier, content, timestamp of creation/modification, and any
/// associated metadata stored as JSON string.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(get_all, skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct SearchedDocument {
    /// Unique identifier for the document, typically generated as a UUID string.
    id: UuidString,
    /// The textual content of the document that was searched and matched.
    content: String,
    /// Timestamp indicating when the document was created or last updated.
    timestamp: TimeStamp,
    /// Optional metadata associated with the document, stored as a JSON string.
    ///
    /// This can include additional contextual information about the document.
    metadata: Option<JsonString>,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl SearchedDocument {
    /// Access the metadata of the document.
    ///
    /// Returns a Python dictionary representation of the document's metadata.
    /// If no metadata exists, returns an empty dictionary.
    fn access_metadata<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyDict>> {
        self.metadata
            .as_ref()
            .map_or(Ok(PyDict::new(python)), |v| utils::to_dict(python, v))
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl StoreDocument {
    /// Create a new Document instance.
    #[new]
    fn new(content: String, vector: Vector, metadata: Option<JsonString>) -> Self {
        Self {
            content,
            vector,
            metadata,
        }
    }

    /// Create a new Document instance with metadata dict.
    #[staticmethod]
    fn with_metadata(
        content: String,
        vector: Vector,
        metadata: Option<Bound<PyDict>>,
    ) -> PyResult<Self> {
        let metadata = metadata
            .map(|obj| {
                depythonize::<Value>(&obj)
                    .into_pyresult()
                    .and_then(|v| serde_json::to_string(&v).into_pyresult())
            })
            .transpose()?;

        Ok(Self {
            content,
            vector,
            metadata,
        })
    }
}

impl SearchedDocument {
    /// Build a SearchedDocument from a single row in a RecordBatch.
    fn from_record_batch_row(batch: &RecordBatch, row_idx: usize) -> PyResult<Self> {
        let id = Self::extract_string_column(batch, ID_FIELD_NAME, row_idx)?;
        let timestamp = Self::extract_i64_column(batch, TIMESTAMP_FIELD_NAME, row_idx)?;
        let content = Self::extract_string_column(batch, CONTENT_FIELD_NAME, row_idx)?;
        let metadata = Self::extract_optional_string_column(batch, METADATA_FIELD_NAME, row_idx)?;

        Ok(Self {
            id,
            content,
            timestamp,
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
    fn extract_i64_column(batch: &RecordBatch, col_name: &str, row_idx: usize) -> PyResult<i64> {
        let array = batch
            .column_by_name(col_name)
            .ok_or_else(|| Self::missing_column_error(col_name))?
            .as_primitive_opt::<Time64MicrosecondType>()
            .ok_or_else(|| Self::invalid_type_error(col_name, "Time64(us)"))?;

        if array.is_null(row_idx) {
            return Err(Self::null_value_error(col_name, row_idx));
        }

        Ok(array.value(row_idx))
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
    fn null_value_error(col_name: &str, row_idx: usize) -> PyErr {
        PyValueError::new_err(format!(
            "Non-nullable column '{}' is null at row {}",
            col_name, row_idx
        ))
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
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
        documents: Vec<StoreDocument>,
        rebuild_index: bool,
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

        table
            .add(
                RecordBatch::try_new(
                    schema_ref.clone(),
                    vec![
                        Arc::new(StringArray::from(id_seq.clone())),
                        Arc::new(Time64MicrosecondArray::from(timestamp_seq)),
                        Arc::new({
                            let vector_field = schema_ref
                                .field_with_name(VECTOR_FIELD_NAME)
                                .expect("vector field in schema");
                            let inner_field: FieldRef = match vector_field.data_type() {
                                DataType::FixedSizeList(f, _) => f.clone(),
                                _ => unreachable!("vector field must be FixedSizeList"),
                            };
                            let arr = FixedSizeListArray::from_iter_primitive::<Float32Type, _, _>(
                                vector_seq, ndim,
                            );

                            FixedSizeListArray::try_new(
                                inner_field,
                                ndim,
                                arr.values().clone(),
                                arr.nulls().cloned(),
                            )
                            .expect("FixedSizeListArray with schema field")
                        }),
                        Arc::new(StringArray::from(content_seq)),
                        Arc::new(StringArray::from(metadata_seq)),
                    ],
                )
                .into_pyresult()?,
            )
            .execute()
            .await
            .into_pyresult()?;

        // Create vector index only when enough rows exist for PQ training (min 256).
        // Small datasets fall back to brute-force scan automatically.
        if rebuild_index && table.count_rows(None).await.into_pyresult()? >= 256 {
            table
                .create_index(&[VECTOR_FIELD_NAME], Index::Auto)
                .execute()
                .await
                .into_pyresult()?;
        }

        Ok(id_seq)
    }

    #[inline]
    fn inject_data(
        documents: Vec<StoreDocument>,
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

    /// Greedily filters rows in nearest-first order, dropping any document whose cosine
    /// similarity with an already-kept document reaches `threshold`, until `limit`
    /// documents are kept or the candidates run out.
    fn dedup_by_cosine(
        rows: Vec<(SearchedDocument, Option<Vector>)>,
        limit: usize,
        threshold: f32,
    ) -> Vec<SearchedDocument> {
        let mut kept_docs: Vec<SearchedDocument> = Vec::with_capacity(limit);
        let mut kept_vectors: Vec<Vector> = Vec::new();

        for (doc, vector) in rows {
            if kept_docs.len() >= limit {
                break;
            }
            match vector {
                // Rows without a comparable vector cannot be judged duplicates.
                None => kept_docs.push(doc),
                Some(vector) => {
                    if !kept_vectors
                        .iter()
                        .any(|kept| utils::cosine_similarity(kept, &vector) >= threshold)
                    {
                        kept_vectors.push(vector);
                        kept_docs.push(doc);
                    }
                }
            }
        }

        kept_docs
    }

    /// Column projection for a search: the vector column is only needed when
    /// cosine deduplication is enabled.
    fn search_columns(dedup: bool) -> Vec<String> {
        let mut columns = vec![
            ID_FIELD_NAME.to_string(),
            TIMESTAMP_FIELD_NAME.to_string(),
            CONTENT_FIELD_NAME.to_string(),
            METADATA_FIELD_NAME.to_string(),
        ];
        if dedup {
            columns.push(VECTOR_FIELD_NAME.to_string());
        }
        columns
    }

    /// Executes one nearest-neighbour query and collects its rows together with
    /// the row vectors (present only when projected).
    async fn query_rows(
        table: Table,
        embedding: Vector,
        fetch_limit: usize,
        columns: Vec<String>,
    ) -> PyResult<Vec<(SearchedDocument, Option<Vector>)>> {
        let batches = table
            .query()
            .nearest_to(embedding)
            .into_pyresult()?
            .limit(fetch_limit)
            .select(Select::Columns(columns))
            .execute()
            .await
            .into_pyresult()?
            .try_collect::<Vec<RecordBatch>>()
            .await
            .into_pyresult()?;

        let mut rows: Vec<(SearchedDocument, Option<Vector>)> = Vec::new();
        for batch in batches {
            for i in 0..batch.num_rows() {
                rows.push((
                    SearchedDocument::from_record_batch_row(&batch, i)?,
                    Self::extract_vector_column(&batch, i)?,
                ));
            }
        }
        Ok(rows)
    }

    /// Runs a single-head search: fetch oversampled candidates when deduplication
    /// is enabled, then greedily filter down to `limit` results.
    async fn search_one(
        table: Table,
        embedding: Vector,
        limit: usize,
        dedup_threshold: Option<f32>,
    ) -> PyResult<Vec<SearchedDocument>> {
        let dedup = dedup_threshold.is_some();
        let fetch_limit = if dedup {
            limit.saturating_mul(DEDUP_OVERSAMPLE_FACTOR)
        } else {
            limit
        };
        let rows =
            Self::query_rows(table, embedding, fetch_limit, Self::search_columns(dedup)).await?;

        Ok(match dedup_threshold {
            None => rows.into_iter().map(|(doc, _)| doc).collect(),
            Some(threshold) => Self::dedup_by_cosine(rows, limit, threshold),
        })
    }

    /// Fuses per-head ranked result lists into one deduplicated list capped at `limit`.
    ///
    /// A head is the raw output of one `search_one` call: its own hits, ordered
    /// best-first by its own embedding and already cosine-deduplicated within itself
    /// when a threshold was given, at most `limit` deep. No score reaches this
    /// function — the position inside a head is the only relevance signal that exists
    /// at this point, and `SearchedDocument` does not carry one — so the budget can
    /// only be spent by rank, never by comparing heads against each other. That is the
    /// point: a global score merge would let the sharpest phrasing take the whole
    /// budget and leave the other heads unrepresented, which defeats the reason for
    /// issuing several heads at all.
    ///
    /// The interleave is rank-major: rank 0 of every head in the given order, then
    /// rank 1 of every head, and so on. Heads too shallow for a rank are skipped
    /// rather than padded, and the walk is lazy — `take` stops it as soon as `limit`
    /// documents have survived, so deeper ranks are never read.
    ///
    /// The deduplication filter keeps the first occurrence of an id, which is that
    /// document's best `(rank, head)` position. Because filtering only removes items,
    /// a later item can move earlier in the handed-out order but never later: a
    /// document two heads agree on costs the later head nothing, it merely makes the
    /// walk reach the next rank, which can only pull more candidates into the result.
    /// Only ids are compared; the same content under different ids is the per-head
    /// cosine deduplication's business, not this function's.
    ///
    /// With `n = heads.len()`, the guarantees are:
    ///
    /// - the result holds `min(limit, distinct ids across the heads)` documents;
    /// - every head's top `limit / n` hits (integer division) are included whenever
    ///   the head has them, and the first `limit % n` heads keep one rank more — the
    ///   remainder goes by position, so the order of `heads` is significant;
    /// - the order stays rank-major, so truncating the result again drops the deepest
    ///   ranks first and keeps per-head diversity.
    ///
    /// Inputs are not defended: `limit == 0` yields an empty result and `limit < n`
    /// lets the earliest heads take everything — keeping `n <= limit` is the caller's
    /// contract, stated on `search_documents`. `seen` is never iterated, only queried
    /// through `insert`'s boolean, so equal inputs always fuse into the same order.
    /// The walk visits `limit` stream positions in the clean case and up to `n * limit`
    /// when heads repeat each other, and the sole allocation is the output: at most
    /// `limit` clones.
    fn fuse_heads(heads: Vec<Vec<SearchedDocument>>, limit: usize) -> Vec<SearchedDocument> {
        let longest = heads.iter().map(Vec::len).max().unwrap_or(0);
        let mut seen = HashSet::new();
        (0..longest)
            .flat_map(|rank| heads.iter().filter_map(move |head| head.get(rank)))
            .filter(|doc| seen.insert(doc.id.as_str()))
            .take(limit)
            .cloned()
            .collect()
    }

    /// Extracts the row's vector column value, returning `None` when the column is absent
    /// from the projection or the cell is null.
    fn extract_vector_column(batch: &RecordBatch, row_idx: usize) -> PyResult<Option<Vector>> {
        let Some(column) = batch.column_by_name(VECTOR_FIELD_NAME) else {
            return Ok(None);
        };
        let Some(list) = column.as_any().downcast_ref::<FixedSizeListArray>() else {
            return Err(PyValueError::new_err(format!(
                "Column '{}' is not of expected type: FixedSizeList",
                VECTOR_FIELD_NAME
            )));
        };

        if list.is_null(row_idx) {
            return Ok(None);
        }

        Ok(Some(
            list.value(row_idx)
                .as_primitive_opt::<Float32Type>()
                .ok_or_else(|| {
                    PyValueError::new_err(format!(
                        "Column '{}' inner values are not of expected type: Float32",
                        VECTOR_FIELD_NAME
                    ))
                })?
                .values()
                .to_vec(),
        ))
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl VectorStoreTable {
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[builtins.list[builtins.str]]", imports = ("typing", "builtins"))
    )]
    #[pyo3(signature = (documents, rebuild_index=true))]
    /// Adds multiple documents to the vector store.
    ///
    /// Args:
    ///     documents: A list of StoreDocument objects to be added to the store.
    ///     rebuild_index: If true (default), rebuild the vector index after adding. Set to false for bulk inserts.
    ///
    /// Returns:
    ///     An awaitable that resolves to a list of document IDs.
    fn add_documents<'a>(
        &self,
        python: Python<'a>,
        documents: Vec<StoreDocument>,
        rebuild_index: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        future_into_py(
            python,
            Self::add_documents_inner(
                self.ndim,
                self.table.clone(),
                self.schema_ref.clone(),
                documents,
                rebuild_index,
            ),
        )
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[None]", imports = ("typing", "builtins"))
    )]
    /// Rebuilds the vector index on the table.
    ///
    /// Useful after bulk inserts with `rebuild_index=False`.
    /// No-op if the table has fewer than 256 rows (minimum for PQ training).
    fn rebuild_index<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        let table = self.table.clone();
        future_into_py(python, async move {
            if table.count_rows(None).await.into_pyresult()? >= 256 {
                table
                    .create_index(&[VECTOR_FIELD_NAME], Index::Auto)
                    .execute()
                    .await
                    .into_pyresult()?;
            }
            Ok(())
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[builtins.list[SearchedDocument]]", imports = ("typing", "builtins"))
    )]
    #[pyo3(signature = (embedding, limit, dedup_threshold=None))]
    /// Searches for documents similar to the given embedding vector.
    ///
    /// Args:
    ///     embedding: A vector representing the query embedding for similarity search.
    ///     limit: The maximum number of similar documents to return.
    ///     dedup_threshold: Optional cosine similarity threshold for semantic deduplication.
    ///         When set, extra candidates are fetched and greedily filtered in nearest-first
    ///         order: a document is dropped once its cosine similarity with an already kept
    ///         document reaches this threshold, so up to `limit` semantically distinct
    ///         documents are returned.
    ///
    /// Returns:
    ///     An awaitable that resolves to a list of SearchedDocument objects.
    fn search_document<'a>(
        &self,
        python: Python<'a>,
        embedding: Vector,
        limit: usize,
        dedup_threshold: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let table = self.table.clone();

        future_into_py(python, async move {
            Self::search_one(table, embedding, limit, dedup_threshold).await
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[builtins.list[SearchedDocument]]", imports = ("typing", "builtins"))
    )]
    #[pyo3(signature = (embeddings, limit, dedup_threshold=None))]
    /// Searches for documents similar to each embedding vector, fusing the per-head rankings into a single deduplicated list.
    ///
    /// All queries execute concurrently inside Rust behind one Python boundary
    /// crossing. Within each head, the cosine deduplication described in
    /// [`search_document`](#method.search_document) applies first; the per-head
    /// rankings are then interleaved round-robin so every query head gets a fair
    /// share of `limit`, a document surfaced by multiple heads is kept once at
    /// its best rank, and the result is capped at `limit` overall.
    ///
    /// Every head is searched to the full `limit` depth before the fusion, so no head
    /// is starved by a pre-allocated share: with `n = len(embeddings)` heads, each
    /// head keeps its own best `limit // n` documents, the first `limit % n` heads
    /// keep one document more, and a head holding fewer hits than its share hands the
    /// rest to the others. No score is compared across heads — that is what keeps the
    /// heads meaningful — so the result comes up short of `limit` only when the heads'
    /// candidates together hold fewer distinct documents. The caller keeps
    /// `n <= limit`; with more heads than budget, the earliest-listed ones take every
    /// slot.
    ///
    /// Args:
    ///     embeddings: A list of query embedding vectors.
    ///     limit: The maximum number of documents to return in total.
    ///     dedup_threshold: Optional per-head cosine similarity deduplication threshold.
    ///
    /// Returns:
    ///     An awaitable that resolves to a list of at most `limit` SearchedDocument objects.
    fn search_documents<'a>(
        &self,
        python: Python<'a>,
        embeddings: Vec<Vector>,
        limit: usize,
        dedup_threshold: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let table = self.table.clone();

        future_into_py(python, async move {
            let searches = embeddings.into_iter().map(|embedding| {
                let table = table.clone();
                async move { Self::search_one(table, embedding, limit, dedup_threshold).await }
            });
            let heads = futures_util::future::try_join_all(searches).await?;
            Ok(Self::fuse_heads(heads, limit))
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreTable>()?;
    m.add_class::<StoreDocument>()?;
    m.add_class::<SearchedDocument>()?;
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::{SearchedDocument, VectorStoreTable};

    fn doc(id: &str, content: &str) -> SearchedDocument {
        SearchedDocument {
            id: id.to_string(),
            content: content.to_string(),
            timestamp: 0,
            metadata: None,
        }
    }

    #[test]
    fn fuse_caps_and_dedups_across_heads() {
        let heads = vec![
            vec![
                doc("id0", "a0"),
                doc("id1", "a1"),
                doc("id2", "a2"),
                doc("id3", "a3"),
            ],
            vec![
                doc("id2", "b0"),
                doc("id10", "b1"),
                doc("id11", "b2"),
                doc("id12", "b3"),
            ],
        ];
        let fused = VectorStoreTable::fuse_heads(heads, 4);
        let contents: Vec<&str> = fused.iter().map(|d| d.content.as_str()).collect();
        assert_eq!(contents, ["a0", "b0", "a1", "b1"]);
    }

    #[test]
    fn fuse_returns_all_distinct_when_budget_exceeds_pool() {
        let heads = vec![
            vec![doc("id0", "a"), doc("id1", "b")],
            vec![doc("id1", "b"), doc("id2", "c")],
        ];
        let fused = VectorStoreTable::fuse_heads(heads, 10);
        let contents: Vec<&str> = fused.iter().map(|d| d.content.as_str()).collect();
        assert_eq!(contents, ["a", "b", "c"]);
    }

    #[test]
    fn fuse_empty_heads_yields_empty() {
        assert!(VectorStoreTable::fuse_heads(vec![], 5).is_empty());
    }
}
