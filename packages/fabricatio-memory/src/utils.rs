use crate::constants::{FIELDS, METADATA_FILE_NAME};
use crate::memory::Memory;
use error_mapping::AsPyErr;
use pyo3::PyResult;
use pyo3::exceptions::PyValueError;
use rayon::iter::IntoParallelIterator;
use rayon::prelude::*;
use std::path::Path;
use tantivy::aggregation::agg_result::{AggregationResult, MetricResult};
use tantivy::query::TermQuery;
use tantivy::schema::IndexRecordOption;
use tantivy::{DocAddress, IndexWriter, Searcher, Term, doc};

pub(crate) fn sanitize_index_name<S: AsRef<str>>(index_name: S) -> PyResult<()> {
    if !sanitize_filename::is_sanitized(index_name.as_ref()) {
        Err(PyValueError::new_err(format!(
            "Invalid index name that contains invalid characters: {}",
            index_name.as_ref()
        )))
    } else {
        Ok(())
    }
}

#[inline]
pub(crate) fn is_valid_index_dir<P: AsRef<Path>>(path: &P) -> bool {
    path.as_ref().join(METADATA_FILE_NAME).exists()
}

#[inline]
pub(crate) fn uuid_query_of(uuid: &str) -> TermQuery {
    let term = Term::from_field_text(FIELDS.uuid, uuid);
    TermQuery::new(term, IndexRecordOption::Basic)
}
#[inline]
pub(crate) fn importance_term_of(importance: u64) -> Term {
    Term::from_field_u64(FIELDS.importance, importance)
}

#[inline]
pub(crate) fn timestamp_term_of(timestamp: i64) -> Term {
    Term::from_field_i64(FIELDS.timestamp, timestamp)
}

#[inline]
pub(crate) fn extract_memory<N: Sized>(items: Vec<(N, Memory)>) -> Vec<Memory> {
    items.into_iter().map(|(_, memory)| memory).collect()
}
#[inline]
pub(crate) fn extract_avg(result: &AggregationResult) -> f64 {
    if let AggregationResult::MetricResult(res) = result
        && let MetricResult::Average(res) = res
        && let Some(avg) = res.value
    {
        avg
    } else {
        0.0
    }
}
#[inline]
pub(crate) fn cast_into_items<N: Sized + Send>(
    searcher: Searcher,
    seq: Vec<(N, DocAddress)>,
) -> Vec<(N, Memory)> {
    seq.into_par_iter()
        .map(|(score, doc_address)| {
            (
                score,
                searcher
                    .doc::<Memory>(doc_address)
                    .expect("Failed to convert doc to Memory"),
            )
        })
        .collect()
}

pub(crate) fn delete_memory_inner(index_writer: &IndexWriter, uuid: &str) {
    let item_uuid = Term::from_field_text(FIELDS.uuid, uuid);
    index_writer.delete_term(item_uuid);
}
pub(crate) fn update_memory_inner(index_writer: &IndexWriter, memory: &Memory) -> PyResult<()> {
    delete_memory_inner(index_writer, memory.uuid.as_str());
    add_memory_inner(index_writer, memory)
}

/// Helper method to add or update a document in the index
pub(crate) fn add_memory_inner(index_writer: &IndexWriter, memory: &Memory) -> PyResult<()> {
    let mut doc = doc!(
        FIELDS.uuid => memory.uuid,
        FIELDS.content => memory.content.as_str(),
        FIELDS.timestamp => memory.timestamp,
        FIELDS.importance => memory.importance,
        FIELDS.access_count => memory.access_count,
        FIELDS.last_accessed => memory.last_accessed
    );
    memory.tags.iter().for_each(|tag| {
        doc.add_text(FIELDS.tags, tag);
    });
    index_writer.add_document(doc).into_pyresult()?;
    Ok(())
}
