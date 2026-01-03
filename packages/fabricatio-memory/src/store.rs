use crate::constants::{field_names, FIELDS, MAX_IMPORTANCE_SCORE};
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
use std::sync::{Arc, Mutex, MutexGuard};
use tantivy::aggregation::agg_req::Aggregations;
use tantivy::aggregation::agg_result::{AggregationResult, MetricResult};
use tantivy::aggregation::AggregationCollector;
use tantivy::collector::TopDocs;
use tantivy::query::*;
use tantivy::{doc, Index, IndexReader, IndexWriter, Order, Score, Searcher};
use utils::mwrap;

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
            reader: Arc::new(index.reader().into_pyresult()?),
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
            w.commit().into_pyresult().map(|_| ())
        } else {
            Ok(())
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl MemoryStore {
    /// Add a new memory to the system and return its ID
    #[pyo3(signature = (content, importance ,tags, write = false))]
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
    #[pyo3(signature = (uuid, write=false))]
    pub fn get_memory(&self, uuid: &str, write: bool) -> PyResult<Option<Memory>> {
        if let Some((_, mut memory)) = self.top(uuid_query_of(uuid))? {
            memory.update_access();
            let mut w = self.access_writer()?;
            update_memory_inner(&w, &memory)?;
            self.write_inner(w, write)?;
            Ok(Some(memory))
        } else {
            Ok(None)
        }
    }

    /// Update an existing memory's content, importance, or tags
    #[pyo3(signature = (uuid, content=None, importance=None, tags=None, write=false))]
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
                let mut w = self.access_writer()?;

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
        let mut w = self.access_writer()?;
        delete_memory_inner(&w, uuid);
        self.write_inner(w, write)?;
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
        let searcher = self.searcher();
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

        // Get the current time
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
