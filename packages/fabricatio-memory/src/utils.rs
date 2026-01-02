use crate::constants::{FIELDS, METADATA_FILE_NAME};
use crate::memory::Memory;
use error_mapping::AsPyErr;
use pyo3::PyResult;
use pyo3::exceptions::PyValueError;
use std::path::Path;
use tantivy::query::TermQuery;
use tantivy::schema::IndexRecordOption;
use tantivy::{IndexWriter, Term, doc};

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

pub(crate) fn is_valid_index_dir<P: AsRef<Path>>(path: &P) -> bool {
    path.as_ref().join(METADATA_FILE_NAME).exists()
}

/// Helper method to convert search results to Memory vector
pub(crate) fn docs_to_memories(
    top_docs: Vec<(f32, tantivy::DocAddress)>,
    searcher: &tantivy::Searcher,
) -> PyResult<Vec<Memory>> {
    let mut memories: Vec<Memory> = Vec::new();
    for (_, doc_address) in top_docs {
        let memory = searcher.doc(doc_address).into_pyresult()?;
        memories.push(memory);
    }
    Ok(memories)
}

pub(crate) fn uuid_query_of(uuid: &str) -> TermQuery {
    let term = Term::from_field_text(FIELDS.uuid, uuid);
    TermQuery::new(term, IndexRecordOption::Basic)
}
pub(crate) fn delete_memory_inner(index_writer: &mut IndexWriter, uuid: &str) {
    let item_uuid = Term::from_field_text(FIELDS.uuid, uuid);
    index_writer.delete_term(item_uuid);
}
pub(crate) fn update_memory_inner(index_writer: &mut IndexWriter, memory: &Memory) -> PyResult<()> {
    delete_memory_inner(index_writer, memory.uuid.as_str());
    add_memory_inner(index_writer, memory)
}

/// Helper method to add or update a document in the index
pub(crate) fn add_memory_inner(index_writer: &mut IndexWriter, memory: &Memory) -> PyResult<()> {
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
