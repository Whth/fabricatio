use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use serde::Deserialize;

/// Memory statistics structure containing aggregated metrics about stored memories
#[derive(Debug, Clone, Default, Deserialize)]
#[gen_stub_pyclass]
#[pyclass(get_all)]
pub struct MemoryStats {
    /// Total number of memories stored
    pub total_memories: u64,
    /// Average importance score across all memories
    pub avg_importance: f64,
    /// Average number of times memories have been accessed
    pub avg_access_count: f64,
    /// Average age of memories in days
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
