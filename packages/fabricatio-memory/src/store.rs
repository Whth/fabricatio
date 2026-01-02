use crate::constants::{field_names, FIELDS, MAX_IMPORTANCE_SCORE, MIN_IMPORTANCE_SCORE};
use crate::memory::Memory;
use crate::service::MemoryService;
use crate::stat::MemoryStats;
use crate::utils::{
    add_memory_inner, cast_into_items, delete_memory_inner, extract_memory, importance_term_of,
    timestamp_term_of, update_memory_inner, uuid_query_of,
};
use chrono::Utc;
use error_mapping::AsPyErr;
use fabricatio_logger::*;
use pyo3::prelude::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods, Bound, PyResult, Python};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use serde::Deserialize;
use std::sync::Arc;
use tantivy::collector::{Count, TopDocs};
use tantivy::query::*;
use tantivy::schema::IndexRecordOption;
use tantivy::{
    doc, DocAddress, Index, IndexReader, IndexWriter, Order, ReloadPolicy, Score, Searcher, Term,
};

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

    fn top_k<Q: Query>(&self, term_query: Q, k: usize) -> PyResult<Vec<(Score, Memory)>> {
        let searcher = self.searcher()?;

        searcher
            .search(&term_query, &TopDocs::with_limit(k))
            .into_pyresult()
            .map(|seq| cast_into_items(searcher, seq))
    }

    fn top<Q: Query>(&self, term_query: Q) -> PyResult<Option<(Score, Memory)>> {
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
        importance: u64,
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
        if let Some((_, mut memory)) = self.top(uuid_query_of(uuid))? {
            memory.update_access();
            let mut w = self.writer()?;
            update_memory_inner(&mut w, &memory)?;
            w.commit().into_pyresult()?;
            Ok(Some(memory))
        } else {
            Ok(None)
        }
    }

    /// Update an existing memory's content, importance, or tags
    #[pyo3(signature = (uuid, content=None, importance=None, tags=None))]
    pub fn update_memory(
        &self,
        uuid: &str,
        content: Option<&str>,
        importance: Option<u64>,
        tags: Option<Vec<String>>,
    ) -> PyResult<bool> {
        if let Some((_, mut memory)) = self.top(uuid_query_of(uuid))? {
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
                let mut w = self.writer()?;

                update_memory_inner(&mut w, &memory)?;
                w.commit().into_pyresult()?;
            }

            Ok(updated)
        } else {
            Ok(false)
        }
    }

    /// Delete a memory by its ID
    pub fn delete_memory(&self, uuid: &str) -> PyResult<bool> {
        let mut w = self.writer()?;
        delete_memory_inner(&mut w, uuid);
        w.commit().into_pyresult()?;
        Ok(true)
    }

    /// Search memories by query string with optional recency boosting
    #[pyo3(signature = (query_str, top_k = 20, boost_recent=false))]
    pub fn search_memories(
        &self,
        query_str: &str,
        top_k: usize,
        boost_recent: bool,
    ) -> PyResult<Vec<Memory>> {
        // Create query parser for content and tags fields following basic example
        let query_parser = QueryParser::for_index(&self.index, vec![FIELDS.content, FIELDS.tags]);
        // Parse query following basic example
        let query = query_parser.parse_query(query_str).into_pyresult()?;
        // Search with TopDocs collector following basic example
        let mut top_docs = self
            .top_k(query, top_k * 2)?
            .into_iter()
            .map(|(score, memory)| {
                (
                    score as f64
                        + if boost_recent {
                        memory.calculate_relevance_score(0.01)
                    } else {
                        0.0
                    },
                    memory,
                )
            })
            .collect::<Vec<(f64, Memory)>>();
        if boost_recent {
            top_docs.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        }
        Ok(top_docs
            .into_iter()
            .take(top_k)
            .map(|(_, memory)| memory)
            .collect())
    }

    /// Search memories by tags
    #[pyo3(signature = (tags, top_k = 20))]
    pub fn search_by_tags(&self, tags: Vec<String>, top_k: usize) -> PyResult<Vec<Memory>> {
        let query_str = tags
            .iter()
            .map(|tag| format!("\"{}\"", tag)) // Ensure tags are treated as phrases
            .collect::<Vec<String>>()
            .join(" OR ");
        self.search_memories(&query_str, top_k, false)
    }

    /// Get memories filtered by minimum importance level
    #[pyo3(signature = (min_importance, top_k = 20))]
    pub fn get_memories_by_importance(
        &self,
        min_importance: u64,
        top_k: usize,
    ) -> PyResult<Vec<Memory>> {
        use std::ops::Bound;
        self.top_k(
            FastFieldRangeQuery::new(
                Bound::Included(importance_term_of(min_importance)),
                Bound::Included(importance_term_of(MAX_IMPORTANCE_SCORE)),
            ),
            top_k,
        )
            .map(extract_memory)
    }

    /// Get memories from the last N days
    #[pyo3(signature = (days, top_k = 20))]
    pub fn get_recent_memories(&self, days: i64, top_k: usize) -> PyResult<Vec<Memory>> {
        let cutoff = Utc::now().timestamp() - (days * 86400);

        use std::ops::Bound;
        self.top_k(
            FastFieldRangeQuery::new(Bound::Included(timestamp_term_of(cutoff)), Bound::Unbounded),
            top_k,
        )
            .map(extract_memory)
    }

    /// Get memories sorted by access frequency
    #[pyo3(signature = (top_k = 20))]
    pub fn get_frequently_accessed(&self, top_k: usize) -> PyResult<Vec<Memory>> {
        let searcher = self.searcher()?;
        searcher
            .search(
                &AllQuery,
                &TopDocs::with_limit(top_k)
                    .order_by_u64_field(field_names::ACCESS_COUNT, Order::Asc),
            )
            .into_pyresult()
            .map(|seq| cast_into_items(searcher, seq))
            .map(extract_memory)
    }


    /// Count the total number of memories in the system
    pub fn count_memories(&self) -> PyResult<u64> {
        self.searcher().map(|s| s.num_docs())
    }

    /// Get aggregated statistics about all memories
    pub fn stats(&self) -> PyResult<MemoryStats> {
        todo!()
    }
}
