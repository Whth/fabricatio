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

/// Validates that an index name contains only valid characters.
///
/// Args:
///     index_name: The index name to validate.
///
/// Returns:
///     PyResult<()> - Ok if valid, Err with message otherwise.
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

/// Checks if a directory contains a valid Tantivy index.
///
/// A valid index directory contains a metadata file.
///
/// Args:
///     path: The directory path to check.
///
/// Returns:
///     True if the directory contains a valid index, False otherwise.
#[inline]
pub(crate) fn is_valid_index_dir<P: AsRef<Path>>(path: &P) -> bool {
    path.as_ref().join(METADATA_FILE_NAME).exists()
}

/// Creates a TermQuery for searching by UUID.
///
/// Args:
///     uuid: The UUID string to query.
///
/// Returns:
///     A TermQuery configured to search the uuid field.
#[inline]
pub(crate) fn uuid_query_of(uuid: &str) -> TermQuery {
    let term = Term::from_field_text(FIELDS.uuid, uuid);
    TermQuery::new(term, IndexRecordOption::Basic)
}

/// Creates a Term for filtering by importance score.
///
/// Args:
///     importance: The importance value to search for.
///
/// Returns:
///     A Term for the importance field.
#[inline]
pub(crate) fn importance_term_of(importance: u64) -> Term {
    Term::from_field_u64(FIELDS.importance, importance)
}

/// Creates a Term for filtering by timestamp.
///
/// Args:
///     timestamp: The timestamp value to search for.
///
/// Returns:
///     A Term for the timestamp field.
#[inline]
pub(crate) fn timestamp_term_of(timestamp: i64) -> Term {
    Term::from_field_i64(FIELDS.timestamp, timestamp)
}

/// Extracts Memory objects from a list of tuples.
///
/// Args:
///     items: A list of tuples containing scores and Memory objects.
///
/// Returns:
///     A list of Memory objects.
#[inline]
pub(crate) fn extract_memory<N: Sized>(items: Vec<(N, Memory)>) -> Vec<Memory> {
    items.into_iter().map(|(_, memory)| memory).collect()
}

/// Extracts the average value from an aggregation result.
///
/// Args:
///     result: The aggregation result to extract from.
///
/// Returns:
///     The average value as f64, or 0.0 if extraction fails.
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

/// Converts a sequence of DocAddresses to Memory objects using a searcher.
///
/// Args:
///     searcher: The Tantivy searcher to use for document retrieval.
///     seq: A sequence of (score, DocAddress) tuples.
///
/// Returns:
///     A list of (score, Memory) tuples.
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

/// Deletes a memory from the index by its UUID.
///
/// Args:
///     index_writer: The index writer to use.
///     uuid: The UUID of the memory to delete.
pub(crate) fn delete_memory_inner(index_writer: &IndexWriter, uuid: &str) {
    let item_uuid = Term::from_field_text(FIELDS.uuid, uuid);
    index_writer.delete_term(item_uuid);
}

/// Updates an existing memory document in the index.
///
/// First deletes the old document, then adds the new one.
///
/// Args:
///     index_writer: The index writer to use.
///     memory: The Memory object to update.
///
/// Returns:
///     PyResult<()> indicating success or failure.
pub(crate) fn update_memory_inner(index_writer: &IndexWriter, memory: &Memory) -> PyResult<()> {
    delete_memory_inner(index_writer, memory.uuid.as_str());
    add_memory_inner(index_writer, memory)
}

/// Adds a memory document to the index.
///
/// Args:
///     index_writer: The index writer to use.
///     memory: The Memory object to add.
///
/// Returns:
///     PyResult<()> indicating success or failure.
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
