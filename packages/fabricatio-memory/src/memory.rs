use chrono::Utc;
use moka::sync::Cache;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tantivy::collector::{Count, TopDocs};
use tantivy::query::QueryParser;
use tantivy::schema::*;

use tantivy::{doc, Index, IndexWriter, ReloadPolicy};

use uuid::{uuid, Timestamp, Uuid};

use crate::constants::field_names::UUID;
pub(crate) use crate::constants::{FIELDS, SCHEMA};
use crate::utils::sanitize_index_name;
use error_mapping::AsPyErr;
use tantivy::directory::MmapDirectory;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[gen_stub_pyclass]
#[pyclass(get_all)]
pub struct Memory {
    pub uuid: String,
    pub content: String,
    pub timestamp: i64,
    pub importance: u64,
    pub tags: Vec<String>,
    pub access_count: u64,
    pub last_accessed: i64,
}

#[gen_stub_pymethods]
#[pymethods]
impl Memory {
    pub fn to_dict<'py>(&self, python: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        Ok(pythonize(python, self)?.cast_into::<PyDict>()?)
    }
}

impl Memory {
    /// Create a new memory with the given parameters
    pub fn new(content: String, importance: u64, tags: Vec<String>) -> Self {
        let now = Utc::now().timestamp();
        Memory {
            uuid: Uuid::now_v7().to_string(),
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
        self.importance as f64 * recency_score * frequency_score
    }
}
