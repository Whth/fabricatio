use chrono::Utc;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pythonize::pythonize;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tantivy::collector::{Count, TopDocs};
use tantivy::query::QueryParser;
use tantivy::schema::*;
use tantivy::{Index, IndexWriter, ReloadPolicy, doc};

pub(crate) use crate::constants::{FIELDS, SCHEMA};
use tantivy::directory::MmapDirectory;

#[derive(Debug, Clone, Default, Deserialize)]
#[pyclass(get_all)]
pub struct MemoryStats {
    pub total_memories: u64,
    pub avg_importance: f64,
    pub avg_access_count: f64,
    pub avg_age_days: f64,
}

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

#[derive(Debug, Clone, Deserialize, Serialize)]
#[pyclass(get_all)]
pub struct Memory {
    pub id: u64,
    pub content: String,
    pub timestamp: i64,
    pub importance: f64,
    pub tags: Vec<String>,
    pub access_count: u64,
    pub last_accessed: i64,
}

#[pymethods]
impl Memory {
    pub fn to_dict<'py>(&self, python: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        Ok(pythonize(python, self)?.cast_into::<PyDict>()?)
    }
}

impl Memory {
    /// Create a new memory with the given parameters
    pub fn new(id: u64, content: String, importance: f64, tags: Vec<String>) -> Self {
        let now = Utc::now().timestamp();
        Memory {
            id,
            content,
            timestamp: now,
            importance,
            tags,
            access_count: 0,
            last_accessed: now,
        }
    }
    /// Update the access count and last accessed timestamp
    pub fn update_access(&mut self) {
        self.access_count += 1;
        self.last_accessed = Utc::now().timestamp();
    }

    /// Calculate relevance score based on importance, recency, and access frequency
    pub fn calculate_relevance_score(&self, decay_factor: f64) -> f64 {
        let time_factor = (Utc::now().timestamp() - self.timestamp) as f64 / 86400.0; // days
        let recency_score = (-time_factor * decay_factor).exp();
        let frequency_score = (self.access_count as f64 + 1.0).ln(); // Add 1 to avoid ln(0) or ln(1)
        self.importance * recency_score * frequency_score
    }
}

#[pyclass]
pub struct MemorySystem {
    index: Index,
    next_id: Arc<Mutex<u64>>,
    writer_buffer_size: usize,
}

impl MemorySystem {
    /// Helper method to convert search results to Memory vector
    fn docs_to_memories(
        &self,
        top_docs: Vec<(f32, tantivy::DocAddress)>,
        searcher: &tantivy::Searcher,
    ) -> PyResult<Vec<Memory>> {
        let mut memories: Vec<Memory> = Vec::new();
        for (_, doc_address) in top_docs {
            let memory = searcher.doc(doc_address).map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to retrieve document: {}", e))
            })?;
            memories.push(memory);
        }
        Ok(memories)
    }

    /// Helper method to add or update a document in the index
    fn add_or_update_document_in_index(
        &self,
        index_writer: &mut IndexWriter,
        memory: &Memory,
    ) -> PyResult<()> {
        let (
            id_field,
            content_field,
            tags_field,
            timestamp_field,
            importance_field,
            access_count_field,
            last_accessed_field,
        ) = *FIELDS;

        let tags_text = memory.tags.join(" ");

        index_writer
            .add_document(doc!(
                id_field => memory.id,
                content_field => memory.content.as_str(),
                timestamp_field => memory.timestamp,
                importance_field => memory.importance,
                tags_field => tags_text,
                access_count_field => memory.access_count,
                last_accessed_field => memory.last_accessed
            ))
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to add/update document: {}", e))
            })?;
        Ok(())
    }
}

#[pymethods]
impl MemorySystem {
    /// Create a new MemorySystem with optional index path and writer buffer size
    #[new]
    #[pyo3(signature = (index_path = None, writer_buffer_size = None))]
    pub fn new(index_path: Option<PathBuf>, writer_buffer_size: Option<usize>) -> PyResult<Self> {
        let schema = SCHEMA.clone();
        let buffer_size = writer_buffer_size.unwrap_or(50_000_000); // Default 50MB

        let index = if let Some(index_directory) = index_path {
            if !index_directory.exists() {
                fs::create_dir_all(&index_directory).map_err(|e| {
                    PyRuntimeError::new_err(format!(
                        "Failed to create index directory '{}': {}",
                        index_directory.display(),
                        e
                    ))
                })?;
            }
            Index::open_or_create(
                MmapDirectory::open(index_directory).map_err(|e| {
                    PyRuntimeError::new_err(format!("Failed to open index directory: {}", e))
                })?,
                schema,
            )
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to open or create index: {}", e))
            })?
        } else {
            Index::create_in_ram(schema)
        };

        Ok(MemorySystem {
            index,
            next_id: Arc::new(Mutex::new(1)),
            writer_buffer_size: buffer_size,
        })
    }

    /// Add a new memory to the system and return its ID
    pub fn add_memory(&self, content: &str, importance: f64, tags: Vec<String>) -> PyResult<u64> {
        let id = {
            let mut next_id = self.next_id.lock().unwrap();
            let current_id = *next_id;
            *next_id += 1;
            current_id
        };

        let memory = Memory::new(id, content.to_string(), importance, tags.clone());

        let mut index_writer: IndexWriter = self
            .index
            .writer(self.writer_buffer_size)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index writer: {}", e)))?;

        self.add_or_update_document_in_index(&mut index_writer, &memory)?;

        index_writer
            .commit()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to commit document: {}", e)))?;

        Ok(id)
    }

    /// Retrieve a memory by its ID and update its access count
    pub fn get_memory(&self, id: u64) -> PyResult<Option<Memory>> {
        let (id_field, ..) = *FIELDS; // Only id_field is needed here for the term query

        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let term = Term::from_field_u64(id_field, id);
        let term_query = tantivy::query::TermQuery::new(term.clone(), IndexRecordOption::Basic);

        let top_docs = searcher
            .search(&term_query, &TopDocs::with_limit(1))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        if let Some((_, doc_address)) = top_docs.first() {
            let mut memory: Memory = searcher.doc(*doc_address).map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to retrieve document: {}", e))
            })?;

            memory.update_access();

            let mut index_writer = self.index.writer(self.writer_buffer_size).map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to get index writer: {}", e))
            })?;

            index_writer.delete_term(term); // Delete the old document

            self.add_or_update_document_in_index(&mut index_writer, &memory)?; // Add the updated document

            index_writer.commit().map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to commit document update: {}", e))
            })?;

            Ok(Some(memory))
        } else {
            Ok(None)
        }
    }

    /// Update an existing memory's content, importance, or tags
    #[pyo3(signature = (id, content=None, importance=None, tags=None))]
    pub fn update_memory(
        &self,
        id: u64,
        content: Option<&str>,
        importance: Option<f64>,
        tags: Option<Vec<String>>,
    ) -> PyResult<bool> {
        let (id_field, ..) = *FIELDS; // Only id_field is needed for the term query

        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let term = Term::from_field_u64(id_field, id);
        let term_query = tantivy::query::TermQuery::new(term.clone(), IndexRecordOption::Basic);

        let top_docs = searcher
            .search(&term_query, &TopDocs::with_limit(1))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        if let Some((_, doc_address)) = top_docs.first() {
            let mut memory: Memory = searcher.doc(*doc_address).map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to retrieve document: {}", e))
            })?;

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
                let mut index_writer = self.index.writer(self.writer_buffer_size).map_err(|e| {
                    PyRuntimeError::new_err(format!("Failed to get index writer: {}", e))
                })?;

                index_writer.delete_term(term.clone()); // term for ID

                self.add_or_update_document_in_index(&mut index_writer, &memory)?;

                index_writer.commit().map_err(|e| {
                    PyRuntimeError::new_err(format!("Failed to commit update: {}", e))
                })?;
            }

            Ok(updated)
        } else {
            Ok(false)
        }
    }

    /// Delete a memory by its ID
    pub fn delete_memory_by_id(&self, id: u64) -> PyResult<bool> {
        let (id_field, _, _, _, _, _, _) = *FIELDS;

        let mut index_writer: IndexWriter = self
            .index
            .writer(self.writer_buffer_size)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index writer: {}", e)))?;
        let term = Term::from_field_u64(id_field, id);
        index_writer.delete_term(term);
        index_writer
            .commit()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to commit deletion: {}", e)))?;

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
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        // Get searcher following basic example
        let searcher = reader.searcher();

        // Create query parser for content and tags fields following basic example
        let query_parser = QueryParser::for_index(&self.index, vec![content_field, tags_field]);

        // Parse query following basic example
        let query = query_parser
            .parse_query(query_str)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to parse query: {}", e)))?;

        // Search with TopDocs collector following basic example
        let top_docs = searcher
            .search(&query, &TopDocs::with_limit(top_k * 2)) // Use a larger limit for relevance scoring
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let mut results = Vec::new();

        // Retrieve documents following basic example pattern
        for (score, doc_address) in top_docs {
            let memory = searcher
                .doc::<Memory>(doc_address)
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to get document: {}", e)))?;

            let combined_score: f64 = if boost_recent {
                Into::<f64>::into(score) + memory.calculate_relevance_score(0.01) // decay_factor could be configurable
            } else {
                Into::<f64>::into(score)
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
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;
        let searcher = reader.searcher();

        // A common strategy is to fetch all (or a large number of) documents first if no better query exists.
        // For very large indexes, this might be inefficient.
        // Tantivy does not directly support filtering and sorting by arbitrary stored fields without specific queries.
        // One might use a NumericRangeQuery if importance was indexed as such, or rely on fetching and filtering.
        let all_query = tantivy::query::AllQuery;
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(10000)) // Fetch up to 10,000 documents to avoid overflow
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search all: {}", e)))?;

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
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(10000)) // Consider if a more targeted query is possible
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

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
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(top_k)) // Consider if a more targeted query is possible
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

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
    ) -> PyResult<Vec<u64>> {
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
                self.delete_memory_by_id(memory.id)
                    .ok()
                    .and_then(|success| if success { Some(memory.id) } else { None })
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
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;
        let searcher = reader.searcher();
        let all_query = tantivy::query::AllQuery;
        let top_docs = searcher
            .search(&all_query, &TopDocs::with_limit(10000)) // Fetch up to 10,000 documents to avoid overflow
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search all: {}", e)))?;
        self.docs_to_memories(top_docs, &searcher)
    }

    /// Count the total number of memories in the system
    pub fn count_memories(&self) -> PyResult<usize> {
        let reader = self
            .index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;
        let searcher = reader.searcher();
        let all_query = tantivy::query::AllQuery;
        let count = searcher
            .search(&all_query, &Count)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to count: {}", e)))?;
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

/// Register Python classes with the module
pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Memory>()?;
    m.add_class::<MemorySystem>()?;
    m.add_class::<MemoryStats>()?;
    Ok(())
}
