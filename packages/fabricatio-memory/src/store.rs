use crate::constants::FIELDS;
use crate::memory::Memory;
use crate::service::MemoryService;
use crate::utils::{add_memory_inner, update_memory_inner, uuid_query_of};
use chrono::Utc;
use error_mapping::AsPyErr;
use pyo3::prelude::{PyModule, PyModuleMethods};
use pyo3::{Bound, PyResult, Python, pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use serde::Deserialize;
use std::sync::Arc;
use tantivy::collector::{Count, TopDocs};
use tantivy::query::{QueryParser, TermQuery};
use tantivy::schema::IndexRecordOption;
use tantivy::{Index, IndexReader, IndexWriter, ReloadPolicy, Searcher, Term, doc};

use rayon::prelude::*;

#[derive(Debug, Clone, Default, Deserialize)]
#[gen_stub_pyclass]
#[pyclass(get_all)]
pub struct MemoryStats {
    pub total_memories: u64,
    pub avg_importance: f64,
    pub avg_access_count: f64,
    pub avg_age_days: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl MemoryStats {
    /// Display memory statistics in a formatted string
    fn display(&self) -> String {
        format!(
            "Total Memories: {}\nAverage Importance: {}\nAverage Access Count: {}\nAverage Age (Days): {}",
            self.total_memories, self.avg_importance, self.avg_access_count, self.avg_age_days
        )
    }
}

#[gen_stub_pyclass]
#[pyclass]
pub struct MemoryStore {
    index: Arc<Index>,
    writer_buffer_size: usize,
}

impl MemoryStore {
    pub fn new(index: Arc<Index>, writer_buffer_size: usize) -> Self {
        Self {
            index,
            writer_buffer_size,
        }
    }
    #[inline]
    fn writer(&self) -> PyResult<IndexWriter> {
        self.index.writer(self.writer_buffer_size).into_pyresult()
    }
    #[inline]
    fn reader(&self) -> PyResult<IndexReader> {
        self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()
    }

    #[inline]
    fn searcher(&self) -> PyResult<Searcher> {
        self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()
            .map(|reader| reader.searcher())
    }

    fn top_k(&self, term_query: TermQuery, k: usize) -> PyResult<Vec<Memory>> {
        let searcher = self.searcher()?;

        searcher
            .search(&term_query, &TopDocs::with_limit(k))
            .into_pyresult()
            .map(|seq| {
                seq.into_par_iter()
                    .map(|(_, doc_address)| searcher.doc::<Memory>(doc_address))
                    .map(|doc| doc.expect("Failed to convert doc to Memory"))
                    .collect()
            })
    }

    fn top(&self, term_query: TermQuery) -> PyResult<Option<Memory>> {
        self.top_k(term_query, 1).map(|mut vec| vec.pop())
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl MemoryStore {
    /// Add a new memory to the system and return its ID
    pub fn add_memory(
        &self,
        content: String,
        importance: f64,
        tags: Vec<String>,
    ) -> PyResult<String> {
        let memory = Memory::new(content, importance, tags);
        let mut w = self.writer()?;
        add_memory_inner(&mut w, &memory)?;
        w.commit().into_pyresult()?;
        Ok(memory.uuid)
    }

    /// Retrieve a memory by its ID and update its access count
    pub fn get_memory(&self, uuid: &str) -> PyResult<Option<Memory>> {
        if let Some(mut mem) = self.top(uuid_query_of(uuid))? {
            mem.update_access();
            let mut w = self.writer()?;
            update_memory_inner(&mut w, &mem)?;
            w.commit().into_pyresult()?;
            Ok(Some(mem))
        } else {
            Ok(None)
        }
    }

    /// Update an existing memory's content, importance, or tags
    #[pyo3(signature = (id, content=None, importance=None, tags=None))]
    pub fn update_memory(
        &self,
        id: &str,
        content: Option<&str>,
        importance: Option<f64>,
        tags: Option<Vec<String>>,
    ) -> PyResult<bool> {
        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;

        let searcher = reader.searcher();
        let term = Term::from_field_text(id_field, id);
        let term_query = tantivy::query::TermQuery::new(term.clone(), IndexRecordOption::Basic);

        let top_docs = searcher
            .search(&term_query, &TopDocs::with_limit(1))
            .into_pyresult()?;

        if let Some((_, doc_address)) = top_docs.first() {
            let mut memory: Memory = searcher.doc(*doc_address).into_pyresult()?;

            let mut updated = false;

            if let Some(new_content) = content {
                memory.content = new_content.to_string();
                updated = true;
            }

            if let Some(new_importance) = importance {
                memory.importance = new_importance;
                updated = true;
            }

            if let Some(new_tags) = tags {
                memory.tags = new_tags;
                updated = true;
            }

            if updated {
                let mut index_writer =
                    self.index.writer(self.writer_buffer_size).into_pyresult()?;

                index_writer.delete_term(term.clone()); // term for ID

                self.add_or_update_document_in_index(&mut index_writer, &memory)?;

                index_writer.commit().into_pyresult()?;
            }

            Ok(updated)
        } else {
            Ok(false)
        }
    }

    /// Delete a memory by its ID
    pub fn delete_memory_by_id(&self, id: &str) -> PyResult<bool> {
        let (id_field, _, _, _, _, _, _) = *FIELDS;

        let mut index_writer: IndexWriter =
            self.index.writer(self.writer_buffer_size).into_pyresult()?;
        let term = Term::from_field_text(id_field, id);
        index_writer.delete_term(term);
        index_writer.commit().into_pyresult()?;

        Ok(true)
    }

    /// Search memories by query string with optional recency boosting
    #[pyo3(signature = (query_str, top_k = 100, boost_recent=false))]
    pub fn search_memories(
        &self,
        query_str: &str,
        top_k: usize,
        boost_recent: bool,
    ) -> PyResult<Vec<Memory>> {
        let (_, content_field, tags_field, _, _, _, _) = *FIELDS;

        // Create reader following basic example pattern
        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;

        // Get searcher following basic example
        let searcher = reader.searcher();

        // Create query parser for content and tags fields following basic example
        let query_parser = QueryParser::for_index(&self.index, vec![content_field, tags_field]);

        // Parse query following basic example
        let query = query_parser.parse_query(query_str).into_pyresult()?;

        // Search with TopDocs collector following basic example
        let top_docs = searcher
            .search(&query, &TopDocs::with_limit(top_k * 2)) // Use a larger limit for relevance scoring
            .into_pyresult()?;

        let mut results = Vec::new();

        // Retrieve documents following basic example pattern
        for (score, doc_address) in top_docs {
            let memory = searcher.doc::<Memory>(doc_address).into_pyresult()?;

            let combined_score: f64 = if boost_recent {
                score as f64 + memory.calculate_relevance_score(0.01) // decay_factor could be configurable
            } else {
                score as f64
            };
            results.push((combined_score, memory));
        }

        // Sort results by combined score in descending order
        results.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        Ok(results
            .into_iter()
            .take(top_k)
            .map(|(_, memory)| memory)
            .collect())
    }

    /// Search memories by tags
    #[pyo3(signature = (tags, top_k = 100))]
    pub fn search_by_tags(&self, tags: Vec<String>, top_k: usize) -> PyResult<Vec<Memory>> {
        let query_str = tags
            .iter()
            .map(|tag| format!("\"{}\"", tag)) // Ensure tags are treated as phrases
            .collect::<Vec<String>>()
            .join(" OR ");
        self.search_memories(&query_str, top_k, false)
    }

    /// Get memories filtered by minimum importance level
    #[pyo3(signature = (min_importance, top_k = 100))]
    pub fn get_memories_by_importance(
        &self,
        min_importance: f64,
        top_k: usize,
    ) -> PyResult<Vec<Memory>> {
        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;
        let searcher = reader.searcher();

        // A common strategy is to fetch all (or a large number of) documents first if no better query exists.
        // For very large indexes, this might be inefficient.
        // Tantivy does not directly support filtering and sorting by arbitrary stored fields without specific queries.
        // One might use a NumericRangeQuery if importance was indexed as such, or rely on fetching and filtering.
        let top_docs = searcher
            .search(&tantivy::query::AllQuery, &TopDocs::with_limit(10000)) // Fetch up to 10,000 documents to avoid overflow
            .into_pyresult()?;

        let mut important_memories = self.docs_to_memories(top_docs, &searcher)?;
        important_memories.retain(|memory| memory.importance >= min_importance);
        important_memories.sort_by(|a, b| {
            b.importance
                .partial_cmp(&a.importance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        Ok(important_memories.into_iter().take(top_k).collect())
    }

    /// Get memories from the last N days
    #[pyo3(signature = (days, top_k = 100))]
    pub fn get_recent_memories(&self, days: i64, top_k: usize) -> PyResult<Vec<Memory>> {
        let cutoff = Utc::now().timestamp() - (days * 86400);

        // Get all documents and filter by timestamp
        let all_query = tantivy::query::AllQuery;

        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;

        let searcher = reader.searcher();
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(10000)) // Consider if a more targeted query is possible
            .into_pyresult()?;

        let mut recent = self.docs_to_memories(top_docs, &searcher)?;
        recent.retain(|memory| memory.timestamp >= cutoff);

        // Sort by timestamp in descending order (most recent first)
        recent.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        Ok(recent.into_iter().take(top_k).collect())
    }

    /// Get memories sorted by access frequency
    #[pyo3(signature = (top_k = 100))]
    pub fn get_frequently_accessed(&self, top_k: usize) -> PyResult<Vec<Memory>> {
        // Get all documents (no filter) and sort by access count
        let all_query = tantivy::query::AllQuery;

        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;

        let searcher = reader.searcher();
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(top_k)) // Consider if a more targeted query is possible
            .into_pyresult()?;

        let mut frequent = self.docs_to_memories(top_docs, &searcher)?;

        frequent.sort_by(|a, b| b.access_count.cmp(&a.access_count));
        Ok(frequent.into_iter().take(top_k).collect())
    }

    /// Clean up old memories based on age, importance, and access frequency
    #[pyo3(signature = (days_threshold, min_importance=0.5, max_access_count=5))]
    pub fn cleanup_old_memories(
        &self,
        days_threshold: i64,
        min_importance: f64,
        max_access_count: u64,
    ) -> PyResult<Vec<String>> {
        let cutoff_timestamp = Utc::now().timestamp() - (days_threshold * 86400);
        let all_memories = self.get_all_memories()?; // Consider more targeted query if performance is an issue

        let removed_ids = all_memories
            .into_iter()
            .filter(|memory| {
                memory.timestamp < cutoff_timestamp
                    && memory.importance < min_importance
                    && memory.access_count < max_access_count
            })
            .filter_map(|memory| {
                self.delete_memory_by_id(memory.uuid.as_str())
                    .ok()
                    .and_then(|success| if success { Some(memory.uuid) } else { None })
            })
            .collect();
        Ok(removed_ids)
    }

    /// Retrieve all memories from the system
    pub fn get_all_memories(&self) -> PyResult<Vec<Memory>> {
        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;
        let searcher = reader.searcher();
        let all_query = tantivy::query::AllQuery;
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(10000)) // Fetch up to 10,000 documents to avoid overflow
            .into_pyresult()?;
        self.docs_to_memories(top_docs, &searcher)
    }

    /// Count the total number of memories in the system
    pub fn count_memories(&self) -> PyResult<usize> {
        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .into_pyresult()?;
        let searcher = reader.searcher();
        let all_query = tantivy::query::AllQuery;
        let count = searcher.search(&all_query, &Count).into_pyresult()?;
        Ok(count)
    }

    /// Get aggregated statistics about all memories
    pub fn get_memory_stats(&self) -> PyResult<MemoryStats> {
        let all_memories = self.get_all_memories()?;

        if all_memories.is_empty() {
            return Ok(MemoryStats::default());
        }

        let total_len = all_memories.len();
        let total_count_f64 = total_len as f64;

        let total_importance: f64 = all_memories.iter().map(|m| m.importance).sum();
        let total_access_count: u64 = all_memories.iter().map(|m| m.access_count).sum();
        let now = Utc::now().timestamp();
        let total_age_seconds: i64 = all_memories.iter().map(|m| now - m.timestamp).sum();

        Ok(MemoryStats {
            total_memories: total_len as u64,
            avg_importance: if total_count_f64 > 0.0 {
                total_importance / total_count_f64
            } else {
                0.0
            },
            avg_access_count: if total_count_f64 > 0.0 {
                total_access_count as f64 / total_count_f64
            } else {
                0.0
            },
            avg_age_days: if total_count_f64 > 0.0 {
                (total_age_seconds as f64) / 86400.0 / total_count_f64
            } else {
                0.0
            },
        })
    }
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Memory>()?;
    m.add_class::<MemoryService>()?;
    m.add_class::<MemoryStats>()?;
    Ok(())
}
