use chrono::Utc;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use serde::{Deserialize, Serialize};

use tantivy::doc;

use crate::constants::MAX_IMPORTANCE_SCORE;
use uuid::Uuid;

/// Represents a memory object with content, importance, tags, and access statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
#[gen_stub_pyclass]
#[pyclass(get_all)]
pub struct Memory {
    /// Unique identifier for the memory
    pub uuid: String,
    /// Content of the memory
    pub content: String,
    /// Unix timestamp when the memory was created
    pub timestamp: i64,
    /// Importance score of the memory (0 to MAX_IMPORTANCE_SCORE)
    pub importance: u64,
    /// List of tags associated with the memory
    pub tags: Vec<String>,
    /// Number of times the memory has been accessed
    pub access_count: u64,
    /// Unix timestamp when the memory was last accessed
    pub last_accessed: i64,
}

#[gen_stub_pymethods]
#[pymethods]
impl Memory {
    /// Convert the memory to a Python dictionary
    pub fn to_dict<'py>(&self, python: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        Ok(pythonize(python, self)?.cast_into::<PyDict>()?)
    }
}

impl Memory {
    /// Create a new memory with the given parameters
    pub fn new(content: String, importance: u64, tags: Vec<String>) -> PyResult<Self> {
        let now = Utc::now().timestamp();

        if importance > MAX_IMPORTANCE_SCORE {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Importance score cannot be greater than {}",
                MAX_IMPORTANCE_SCORE
            )));
        }

        Ok(Memory {
            uuid: Uuid::now_v7().to_string(),
            content,
            timestamp: now,
            importance,
            tags,
            access_count: 0,
            last_accessed: now,
        })
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
