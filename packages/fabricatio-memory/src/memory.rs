use chrono::Utc;
use jieba_rs::Jieba;
use once_cell::sync::Lazy;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use serde::Deserialize;
use std::sync::{Arc, Mutex};
use tantivy::collector::TopDocs;
use tantivy::query::QueryParser;
use tantivy::schema::document::{DeserializeError, DocumentDeserialize, DocumentDeserializer};
use tantivy::schema::*;
use tantivy::tokenizer::TextAnalyzer;
use tantivy::{doc, Document, Index, IndexWriter, ReloadPolicy, TantivyDocument};

use serde_json::value::Value;

static SCHEMA: Lazy<Schema> = Lazy::new(|| {
    let mut schema_builder = Schema::builder();

    schema_builder.add_u64_field("id", STORED | INDEXED);
    schema_builder.add_text_field("content", TEXT | STORED);
    schema_builder.add_text_field("tags", TEXT | STORED);
    schema_builder.add_i64_field("timestamp", STORED | INDEXED);
    schema_builder.add_f64_field("importance", STORED | INDEXED);
    schema_builder.add_u64_field("access_count", STORED | INDEXED);
    schema_builder.add_i64_field("last_accessed", STORED | INDEXED);

    schema_builder.build()
});

static FIELDS: Lazy<(Field, Field, Field, Field, Field, Field, Field)> = Lazy::new(|| {
    let id_field = SCHEMA.get_field("id").unwrap();
    let content_field = SCHEMA.get_field("content").unwrap();
    let tags_field = SCHEMA.get_field("tags").unwrap();
    let timestamp_field = SCHEMA.get_field("timestamp").unwrap();
    let importance_field = SCHEMA.get_field("importance").unwrap();
    let access_count_field = SCHEMA.get_field("access_count").unwrap();
    let last_accessed_field = SCHEMA.get_field("last_accessed").unwrap();

    (id_field, content_field, tags_field, timestamp_field, importance_field, access_count_field, last_accessed_field)
});


impl DocumentDeserialize for Memory {
    fn deserialize<'de, D>(deserializer: D) -> Result<Self, DeserializeError>
    where
        D: DocumentDeserializer<'de>,
    {
        let o: String = TantivyDocument::deserialize(deserializer)?.to_json(&SCHEMA);

        let v = serde_json::from_str::<Value>(o.as_str()).expect("Failed to deserialize JSON");

        Ok(Memory {
            id: v.get("id").expect("Field 'id' missing").as_array().unwrap().first().unwrap().as_u64().expect("Field 'id' is not a u64"),
            content: v.get("content").expect("Field 'content' missing").as_array().unwrap().first().unwrap().as_str()
                .expect("Field 'content' is not a string")
                .to_string(),
            timestamp: v.get("timestamp").expect("Field 'timestamp' missing").as_array().unwrap().first().unwrap().as_i64()
                .expect("Field 'timestamp' is not an i64"),
            importance: v.get("importance").expect("Field 'importance' missing").as_array().unwrap().first().unwrap().as_f64()
                .expect("Field 'importance' is not an f64"),
            tags: v.get("tags").expect("Field 'tags' missing").as_array().unwrap().first().unwrap().to_string()
                .split_whitespace()
                .map(|s| s.to_string())
                .collect(),
            access_count: v.get("access_count").expect("Field 'access_count' missing").as_array().unwrap().first().unwrap().as_u64()
                .expect("Field 'access_count' is not a u64"),
            last_accessed: v.get("last_accessed").expect("Field 'last_accessed' missing").as_array().unwrap().first().unwrap().as_i64()
                .expect("Field 'last_accessed' is not an i64"),
        })
    }
}

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
    fn display(&self) -> String {
        format!("Total Memories: {}\nAverage Importance: {}\nAverage Access Count: {}\nAverage Age (Days): {}",
                self.total_memories,
                self.avg_importance,
                self.avg_access_count,
                self.avg_age_days)
    }
}


#[derive(Debug, Clone, Deserialize)]
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
    #[new]
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

    pub fn update_access(&mut self) {
        self.access_count += 1;
        self.last_accessed = Utc::now().timestamp();
    }

    pub fn calculate_relevance_score(&self, decay_factor: f64) -> f64 {
        let time_factor = (Utc::now().timestamp() - self.timestamp) as f64 / 86400.0; // days
        let recency_score = (-time_factor * decay_factor).exp();
        let frequency_score = (self.access_count as f64).ln() + 1.0;
        self.importance * recency_score * frequency_score
    }
}

#[pyclass]
pub struct MemorySystem {
    index: Index,
    jieba: Jieba,
    next_id: Arc<Mutex<u64>>,
}

impl MemorySystem {
    // Helper method to convert search results to Memory vector
    fn docs_to_memories(&self, top_docs: Vec<(f32, tantivy::DocAddress)>, searcher: &tantivy::Searcher) -> PyResult<Vec<Memory>> {
        let mut memories: Vec<Memory> = Vec::new();
        for (_, doc_address) in top_docs {
            let memory = searcher.doc::<Memory>(doc_address).map_err(|e| PyRuntimeError::new_err(format!("Failed to get document: {}", e)))?;
            memories.push(memory);
        }
        Ok(memories)
    }
}

#[pymethods]
impl MemorySystem {
    #[new]
    pub fn new() -> PyResult<Self> {
        // Create index in RAM using the static schema
        let index = Index::create_in_ram(SCHEMA.clone());

        // Register Jieba tokenizer
        let jieba_tokenizer = JiebaTokenizer { jieba: Jieba::new() };
        index.tokenizers().register("jieba", TextAnalyzer::from(jieba_tokenizer));

        Ok(MemorySystem {
            index,
            jieba: Jieba::new(),
            next_id: Arc::new(Mutex::new(1)),
        })
    }

    pub fn add_memory(&self, content: &str, importance: f64, tags: Vec<String>) -> PyResult<u64> {
        let id = {
            let mut next_id = self.next_id.lock().unwrap();
            let current_id = *next_id;
            *next_id += 1;
            current_id
        };

        let memory = Memory::new(id, content.to_string(), importance, tags.clone());

        // Create index writer following basic example pattern
        let mut index_writer: IndexWriter = self.index.writer(50_000_000)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index writer: {}", e)))?;

        let tags_text = tags.join(" ");
        let (id_field, content_field, tags_field, timestamp_field, importance_field, access_count_field, last_accessed_field) = *FIELDS;

        // Add document using doc! macro following basic example
        index_writer.add_document(doc!(
            id_field => id,
            content_field => content,
            timestamp_field => memory.timestamp,
            importance_field => importance,
            tags_field => tags_text,
            access_count_field => memory.access_count as u64,
            last_accessed_field => memory.last_accessed
        ))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to add document: {}", e)))?;

        // Commit changes following basic example
        index_writer.commit()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to commit document: {}", e)))?;

        Ok(id)
    }

    pub fn get_memory(&self, id: u64) -> PyResult<Option<Memory>> {
        let (id_field, content_field, tags_field, timestamp_field, importance_field, access_count_field, last_accessed_field) = *FIELDS;

        // Create reader to search for memory by ID
        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let term = Term::from_field_u64(id_field, id);
        let term_query = tantivy::query::TermQuery::new(term, tantivy::schema::IndexRecordOption::Basic);

        let top_docs = searcher.search(&term_query, &TopDocs::with_limit(1))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        if let Some((_, doc_address)) = top_docs.first() {
            let mut memory = searcher.doc::<Memory>(*doc_address).map_err(|e| PyRuntimeError::new_err(format!("Failed to get document: {}", e)))?;

            // Update access count and last accessed time
            memory.update_access();

            // Update the document in the index
            let mut index_writer = self.index.writer(50_000_000)
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index writer: {}", e)))?;

            // Delete old document
            let term = Term::from_field_u64(id_field, id);
            index_writer.delete_term(term);

            // Add updated document
            let tags_text = memory.tags.join(" ");
            index_writer.add_document(doc!(
                id_field => memory.id,
                content_field => memory.content.as_str(),
                timestamp_field => memory.timestamp,
                importance_field => memory.importance,
                tags_field => tags_text,
                access_count_field => memory.access_count,
                last_accessed_field => memory.last_accessed
            ))
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to add document: {}", e)))?;

            index_writer.commit()
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to commit document: {}", e)))?;

            Ok(Some(memory))
        } else {
            Ok(None)
        }
    }

    #[pyo3(signature = (id, content=None, importance=None, tags=None))]
    pub fn update_memory(&self, id: u64, content: Option<&str>, importance: Option<f64>, tags: Option<Vec<String>>) -> PyResult<bool> {
        let (id_field, _, _, _, _, _, _) = *FIELDS;

        // First, get the existing memory
        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let term = Term::from_field_u64(id_field, id);
        let term_query = tantivy::query::TermQuery::new(term, tantivy::schema::IndexRecordOption::Basic);

        let top_docs = searcher.search(&term_query, &TopDocs::with_limit(1))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        if let Some((_, doc_address)) = top_docs.first() {
            let mut memory = searcher.doc::<Memory>(*doc_address).map_err(|e| PyRuntimeError::new_err(format!("Failed to get document: {}", e)))?;

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
                // Update search index
                self.delete_memory_by_id(id)?;
                self.add_memory(&memory.content, memory.importance, memory.tags)?;
            }

            Ok(updated)
        } else {
            Ok(false)
        }
    }

    pub fn delete_memory_by_id(&self, id: u64) -> PyResult<bool> {
        let (id_field, _, _, _, _, _, _) = *FIELDS;

        let mut index_writer: IndexWriter = self.index.writer(50_000_000)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index writer: {}", e)))?;
        let term = Term::from_field_u64(id_field, id);
        index_writer.delete_term(term);
        index_writer.commit()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to commit deletion: {}", e)))?;

        Ok(true)
    }

    #[pyo3(signature = (query_str, top_k, boost_recent=false))]
    pub fn search_memories(&self, query_str: &str, top_k: usize, boost_recent: bool) -> PyResult<Vec<Memory>> {
        let (_, content_field, tags_field, _, _, _, _) = *FIELDS;

        // Create reader following basic example pattern
        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        // Get searcher following basic example
        let searcher = reader.searcher();

        // Create query parser for content and tags fields following basic example
        let query_parser = QueryParser::for_index(&self.index, vec![content_field, tags_field]);

        // Parse query following basic example
        let query = query_parser.parse_query(query_str)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to parse query: {}", e)))?;

        // Search with TopDocs collector following basic example
        let top_docs = searcher.search(&query, &TopDocs::with_limit(top_k * 2))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let mut results = Vec::new();

        // Retrieve documents following basic example pattern
        for (score, doc_address) in top_docs {
            let memory = searcher.doc::<Memory>(doc_address).map_err(|e| PyRuntimeError::new_err(format!("Failed to get document: {}", e)))?;

            let combined_score: f64 = if boost_recent {
                Into::<f64>::into(score) + memory.calculate_relevance_score(0.01)
            } else {
                Into::<f64>::into(score)
            };
            results.push((combined_score, memory));
        }

        // Sort results by combined score in descending order
        results.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        Ok(results.into_iter().take(top_k).map(|(_, memory)| memory).collect())
    }

    pub fn search_by_tags(&self, tags: Vec<String>, top_k: usize) -> PyResult<Vec<Memory>> {
        let query_str = tags.join(" OR ");
        self.search_memories(&query_str, top_k, false)
    }

    pub fn get_memories_by_importance(&self, min_importance: f64, top_k: usize) -> PyResult<Vec<Memory>> {
        // Get all documents and filter by importance
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher.search(&all_query, &TopDocs::with_limit(10000))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let mut important = self.docs_to_memories(top_docs, &searcher)?;
        important.retain(|memory| memory.importance >= min_importance);

        // Sort by importance in descending order
        important.sort_by(|a, b| b.importance.partial_cmp(&a.importance).unwrap_or(std::cmp::Ordering::Equal));
        Ok(important.into_iter().take(top_k).collect())
    }

    pub fn get_recent_memories(&self, days: i64, top_k: usize) -> PyResult<Vec<Memory>> {
        let cutoff = Utc::now().timestamp() - (days * 86400);

        // Get all documents and filter by timestamp
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher.search(&all_query, &TopDocs::with_limit(10000))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let mut recent = self.docs_to_memories(top_docs, &searcher)?;
        recent.retain(|memory| memory.timestamp >= cutoff);

        // Sort by timestamp in descending order (most recent first)
        recent.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        Ok(recent.into_iter().take(top_k).collect())
    }

    pub fn get_frequently_accessed(&self, top_k: usize) -> PyResult<Vec<Memory>> {
        // Get all documents (no filter) and sort by access count
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher.search(&all_query, &TopDocs::with_limit(10000))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let mut frequent = self.docs_to_memories(top_docs, &searcher)?;

        frequent.sort_by(|a, b| b.access_count.cmp(&a.access_count));
        Ok(frequent.into_iter().take(top_k).collect())
    }

    pub fn consolidate_memories(&self, similarity_threshold: f64) -> PyResult<Vec<(u64, u64)>> {
        // Get all memories from the index
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher.search(&all_query, &TopDocs::with_limit(10000))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let memories = self.docs_to_memories(top_docs, &searcher)?;

        let mut consolidated_pairs = Vec::new();
        for i in 0..memories.len() {
            for j in (i + 1)..memories.len() {
                let similarity = self.calculate_content_similarity(&memories[i].content, &memories[j].content);
                if similarity > similarity_threshold {
                    consolidated_pairs.push((memories[i].id, memories[j].id));
                }
            }
        }

        Ok(consolidated_pairs)
    }

    pub fn cleanup_old_memories(&self, days_threshold: i64, min_importance: f64) -> PyResult<Vec<u64>> {
        let cutoff = Utc::now().timestamp() - (days_threshold * 86400);

        // Get all memories from the index
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher.search(&all_query, &TopDocs::with_limit(10000))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        let memories = self.docs_to_memories(top_docs, &searcher)?;

        let to_remove: Vec<u64> = memories.iter()
            .filter(|memory| memory.timestamp < cutoff && memory.importance < min_importance && memory.access_count < 5)
            .map(|memory| memory.id)
            .collect();

        for id in &to_remove {
            self.delete_memory_by_id(*id)?;
        }

        Ok(to_remove)
    }

    pub fn get_all_memories(&self) -> PyResult<Vec<Memory>> {
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let top_docs = searcher.search(&all_query, &TopDocs::with_limit(10000))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to search: {}", e)))?;

        self.docs_to_memories(top_docs, &searcher)
    }

    pub fn count_memories(&self) -> PyResult<usize> {
        let all_query = tantivy::query::AllQuery;

        let reader = self.index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to get index reader: {}", e)))?;

        let searcher = reader.searcher();
        let count = searcher.search(&all_query, &tantivy::collector::Count)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to count: {}", e)))?;

        Ok(count)
    }

    pub fn get_memory_stats(&self) -> PyResult<MemoryStats> {
        let all_memories = self.get_all_memories()?;

        if all_memories.is_empty() {
            return Ok(MemoryStats::default());
        }

        let total_count = all_memories.len() as f64;
        let total_importance: f64 = all_memories.iter().map(|m| m.importance).sum();
        let total_access_count: u64 = all_memories.iter().map(|m| m.access_count).sum();
        let now = Utc::now().timestamp();
        let total_age: i64 = all_memories.iter().map(|m| now - m.timestamp).sum();

        Ok(MemoryStats {
            total_memories: total_count as u64,
            avg_importance: total_importance / total_count,
            avg_access_count: total_access_count as f64 / total_count,
            avg_age_days: (total_age as f64) / 86400.0 / total_count,
        })
    }

    fn calculate_content_similarity(&self, content1: &str, content2: &str) -> f64 {
        // Simple Jaccard similarity using Jieba tokenization
        let tokens1: std::collections::HashSet<_> = self.jieba
            .tokenize(content1, jieba_rs::TokenizeMode::Search, true)
            .into_iter()
            .map(|t| t.word)
            .collect();

        let tokens2: std::collections::HashSet<_> = self.jieba
            .tokenize(content2, jieba_rs::TokenizeMode::Search, true)
            .into_iter()
            .map(|t| t.word)
            .collect();

        let intersection_size = tokens1.intersection(&tokens2).count() as f64;
        let union_size = tokens1.union(&tokens2).count() as f64;

        if union_size == 0.0 {
            0.0
        } else {
            intersection_size / union_size
        }
    }
}

// Custom Jieba Tokenizer for Tantivy
#[derive(Clone)]
struct JiebaTokenizer {
    jieba: Jieba,
}

impl tantivy::tokenizer::Tokenizer for JiebaTokenizer {
    type TokenStream<'a> = JiebaTokenStream;

    fn token_stream<'a>(&'a mut self, text: &'a str) -> Self::TokenStream<'a> {
        let jieba_tokens = self.jieba.tokenize(text, jieba_rs::TokenizeMode::Search, true);
        let mut tantivy_tokens = Vec::with_capacity(jieba_tokens.len());
        let mut position_counter = 0;
        for jt in jieba_tokens {
            tantivy_tokens.push(tantivy::tokenizer::Token {
                offset_from: jt.start,
                offset_to: jt.end,
                position: position_counter,
                text: jt.word.to_string(),
                position_length: 1,
            });
            position_counter += 1;
        }
        JiebaTokenStream {
            tokens: tantivy_tokens,
            index: 0,
        }
    }
}

struct JiebaTokenStream {
    tokens: Vec<tantivy::tokenizer::Token>,
    index: usize,
}

impl<'a> tantivy::tokenizer::TokenStream for JiebaTokenStream {
    fn advance(&mut self) -> bool {
        if self.index < self.tokens.len() {
            self.index += 1;
            true
        } else {
            false
        }
    }

    fn token(&self) -> &tantivy::tokenizer::Token {
        &self.tokens[self.index - 1]
    }

    fn token_mut(&mut self) -> &mut tantivy::tokenizer::Token {
        &mut self.tokens[self.index - 1]
    }
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Memory>()?;
    m.add_class::<MemorySystem>()?;
    Ok(())
}