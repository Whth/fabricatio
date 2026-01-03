use crate::constants::{FIELDS, MAX_IMPORTANCE_SCORE, field_names};
use crate::memory::Memory;
use crate::stat::MemoryStats;
use crate::utils::{
    add_memory_inner, cast_into_items, delete_memory_inner, extract_avg, extract_memory,
    importance_term_of, timestamp_term_of, update_memory_inner, uuid_query_of,
};
use chrono::Utc;
use error_mapping::AsPyErr;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use rayon::prelude::*;
use std::sync::{Arc, Mutex, MutexGuard};
use tantivy::aggregation::AggregationCollector;
use tantivy::aggregation::agg_req::Aggregations;
use tantivy::aggregation::agg_result::{AggregationResult, MetricResult};
use tantivy::collector::TopDocs;
use tantivy::query::*;
use tantivy::{Index, IndexReader, IndexWriter, Order, ReloadPolicy, Score, Searcher, doc};
use utils::mwrap;

/// MemoryStore is a struct that provides an interface for storing, retrieving, and searching memories
/// in a Tantivy search index. It supports operations such as adding, updating, deleting, and searching
/// memories based on various criteria like content, tags, importance, recency, and access frequency.
///
/// The store handles memory access tracking by updating access counts and timestamps automatically
/// during retrieval and search operations. It also supports batch updates and optional immediate
/// disk writes for consistency.
///
/// The implementation uses a Tantivy index with fields for content, tags, importance, timestamps,
/// and access counts. It includes PyO3 bindings to allow Python usage.
#[gen_stub_pyclass]
#[pyclass]
pub struct MemoryStore {
    index: Arc<Index>,
    writer: Arc<Mutex<IndexWriter>>,
    reader: Arc<IndexReader>,
}

impl MemoryStore {
    pub fn new(index: Arc<Index>, writer_buffer_size: usize) -> PyResult<Self> {
        Ok(Self {
            index: index.clone(),
            writer: mwrap(index.writer(writer_buffer_size).into_pyresult()?),
            reader: Arc::new(
                index
                    .reader_builder()
                    .reload_policy(ReloadPolicy::Manual)
                    .try_into()
                    .into_pyresult()?,
            ),
        })
    }
    #[inline]
    fn searcher(&self) -> Searcher {
        self.reader.searcher()
    }

    #[inline(always)]
    fn access_writer(&'_ self) -> PyResult<MutexGuard<'_, IndexWriter>> {
        self.writer.lock().into_pyresult()
    }

    fn top_k<Q: Query>(&self, term_query: Q, k: usize) -> PyResult<Vec<(Score, Memory)>> {
        let searcher = self.searcher();

        searcher
            .search(&term_query, &TopDocs::with_limit(k))
            .into_pyresult()
            .map(|seq| cast_into_items(searcher, seq))
    }

    fn top<Q: Query>(&self, term_query: Q) -> PyResult<Option<(Score, Memory)>> {
        self.top_k(term_query, 1).map(|mut vec| vec.pop())
    }

    #[inline]
    fn write_inner(&self, mut w: MutexGuard<IndexWriter>, write_now: bool) -> PyResult<()> {
        if write_now {
            w.commit().into_pyresult()?;
            self.reader.reload().into_pyresult()
        } else {
            Ok(())
        }
    }

    // --- Helper function for batch access updates ---
    /// Updates the access count and last_accessed timestamp for a batch of memories
    /// in the writer, and optionally writes changes to disk.
    ///
    /// This function does NOT take ownership of the input memories for the update,
    /// but returns the original input.
    fn update_access_and_write_batch(
        &self,
        memories: Vec<Memory>,
        write: bool,
    ) -> PyResult<Vec<Memory>> {
        if memories.is_empty() {
            return Ok(memories);
        }

        let w = self.access_writer()?;
        // Update each memory's access info and stage the update in the writer
        memories
            .par_iter()
            .cloned()
            .map(|mut mem| {
                mem.update_access();
                mem
            })
            .collect::<Vec<Memory>>()
            .iter()
            .try_for_each(|mem| update_memory_inner(&w, mem))?;

        // Only flush to disk if `write` is true
        self.write_inner(w, write)?;
        Ok(memories)
    }
}
#[gen_stub_pymethods]
#[pymethods]
impl MemoryStore {
    /// Add a new memory to the system and return its ID
    #[pyo3(signature = (content, importance, tags, write = false))]
    pub fn add_memory(
        &mut self,
        content: String,
        importance: u64,
        tags: Vec<String>,
        write: bool,
    ) -> PyResult<String> {
        let memory = Memory::new(content, importance, tags)?;
        let w = self.access_writer()?;

        add_memory_inner(&w, &memory)?;
        self.write_inner(w, write)?;
        Ok(memory.uuid)
    }

    /// Write all changes to disk
    pub fn write(&self) -> PyResult<()> {
        self.write_inner(self.writer.lock().into_pyresult()?, true)
    }

    /// Retrieve a memory by its ID and update its access count
    #[pyo3(signature = (uuid, write = false))]
    pub fn get_memory(&self, uuid: &str, write: bool) -> PyResult<Option<Memory>> {
        if let Some((_, mut memory)) = self.top(uuid_query_of(uuid))? {
            memory.update_access();
            let w = self.access_writer()?;
            update_memory_inner(&w, &memory)?;
            self.write_inner(w, write)?;
            Ok(Some(memory))
        } else {
            Ok(None)
        }
    }

    /// Update an existing memory's content, importance, or tags
    #[pyo3(signature = (uuid, content = None, importance = None, tags = None, write = false))]
    pub fn update_memory(
        &self,
        uuid: &str,
        content: Option<&str>,
        importance: Option<u64>,
        tags: Option<Vec<String>>,
        write: bool,
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
                let w = self.access_writer()?;
                update_memory_inner(&w, &memory)?;
                self.write_inner(w, write)?;
            }

            Ok(updated)
        } else {
            Ok(false)
        }
    }

    /// Delete a memory by its ID
    #[pyo3(signature = (uuid, write = false))]
    pub fn delete_memory(&self, uuid: &str, write: bool) -> PyResult<bool> {
        let w = self.access_writer()?;
        delete_memory_inner(&w, uuid);
        self.write_inner(w, write)?;
        Ok(true)
    }

    /// Search memories by query string with optional recency boosting
    #[pyo3(signature = (query_str, top_k = 20, boost_recent = false, write = false))]
    pub fn search_memories(
        &self,
        query_str: &str,
        top_k: usize,
        boost_recent: bool,
        write: bool,
    ) -> PyResult<Vec<Memory>> {
        let query_parser = QueryParser::for_index(&self.index, vec![FIELDS.content, FIELDS.tags]);
        let query = query_parser.parse_query(query_str).into_pyresult()?;

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

        let retrieved_memories: Vec<Memory> = top_docs
            .into_iter()
            .take(top_k)
            .map(|(_, memory)| memory)
            .collect();

        self.update_access_and_write_batch(retrieved_memories, write)
    }

    /// Search memories by tags
    #[pyo3(signature = (tags, top_k = 20, write = false))]
    pub fn search_by_tags(
        &self,
        tags: Vec<String>,
        top_k: usize,
        write: bool,
    ) -> PyResult<Vec<Memory>> {
        let query_str = tags
            .iter()
            .map(|tag| format!("\"{}\"", tag))
            .collect::<Vec<String>>()
            .join(" OR ");
        self.search_memories(&query_str, top_k, false, write)
    }

    /// Get memories filtered by minimum importance level
    #[pyo3(signature = (min_importance, top_k = 20, write = false))]
    pub fn get_memories_by_importance(
        &self,
        min_importance: u64,
        top_k: usize,
        write: bool,
    ) -> PyResult<Vec<Memory>> {
        use std::ops::Bound;
        let memories = self
            .top_k(
                FastFieldRangeQuery::new(
                    Bound::Included(importance_term_of(min_importance)),
                    Bound::Included(importance_term_of(MAX_IMPORTANCE_SCORE)),
                ),
                top_k,
            )
            .map(extract_memory)?;

        self.update_access_and_write_batch(memories, write)
    }

    /// Get memories from the last N days
    #[pyo3(signature = (days, top_k = 20, write = false))]
    pub fn get_recent_memories(
        &self,
        days: i64,
        top_k: usize,
        write: bool,
    ) -> PyResult<Vec<Memory>> {
        let cutoff = Utc::now().timestamp() - (days * 86400);

        use std::ops::Bound;
        let memories = self
            .top_k(
                FastFieldRangeQuery::new(
                    Bound::Included(timestamp_term_of(cutoff)),
                    Bound::Unbounded,
                ),
                top_k,
            )
            .map(extract_memory)?;

        self.update_access_and_write_batch(memories, write)
    }

    /// Get memories sorted by access frequency
    #[pyo3(signature = (top_k = 20, write = false))]
    pub fn get_frequently_accessed(&self, top_k: usize, write: bool) -> PyResult<Vec<Memory>> {
        let searcher = self.searcher();
        let memories = searcher
            .search(
                &AllQuery,
                &TopDocs::with_limit(top_k)
                    .order_by_u64_field(field_names::ACCESS_COUNT, Order::Desc), // Fixed: Desc for most frequent
            )
            .into_pyresult()
            .map(|seq| cast_into_items(searcher, seq))
            .map(extract_memory)?;

        self.update_access_and_write_batch(memories, write)
    }

    /// Count the total number of memories in the system
    pub fn count_memories(&self) -> u64 {
        self.searcher().num_docs()
    }

    /// Get aggregated statistics about all memories
    pub fn stats(&self) -> PyResult<MemoryStats> {
        let searcher = self.searcher();

        let agg_req_json = format!(
            r#"
        {{
            "total_memories": {{ "value_count": {{ "field": "{}" }} }},
            "avg_importance": {{ "avg": {{ "field": "{}" }} }},
            "avg_access_count": {{ "avg": {{ "field": "{}" }} }},
            "avg_timestamp": {{ "avg": {{ "field": "{}" }} }}
        }}
        "#,
            field_names::UUID,
            field_names::IMPORTANCE,
            field_names::ACCESS_COUNT,
            field_names::TIMESTAMP
        );

        let aggs: Aggregations = serde_json::from_str(&agg_req_json).into_pyresult()?;

        let collector = AggregationCollector::from_aggs(aggs, Default::default());
        let result = searcher.search(&AllQuery, &collector).into_pyresult()?.0;

        let total_memories = if let AggregationResult::MetricResult(res) = result
            .get("total_memories")
            .expect("total_memories aggregation must exist")
            && let MetricResult::Count(res) = res
            && let Some(count) = res.value
        {
            count as u64
        } else {
            0
        };

        let avg_importance = extract_avg(
            result
                .get("avg_importance")
                .expect("avg_importance aggregation must exist"),
        );

        let avg_access_count = extract_avg(
            result
                .get("avg_access_count")
                .expect("avg_access_count aggregation must exist"),
        );

        let avg_timestamp = extract_avg(
            result
                .get("avg_timestamp")
                .expect("avg_timestamp aggregation must exist"),
        );

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs() as f64)
            .unwrap_or(0.0);

        let avg_age_days = if avg_timestamp > 0.0 {
            (now - avg_timestamp) / (24.0 * 3600.0)
        } else {
            0.0
        };

        Ok(MemoryStats {
            total_memories,
            avg_importance,
            avg_access_count,
            avg_age_days,
        })
    }
}
