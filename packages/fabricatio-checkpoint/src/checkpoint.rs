//! Shadow repository management for file checkpointing.
//!
//! This module provides a Python-accessible interface for managing shadow Git repositories
//! that track file changes and enable checkpoint/restore functionality. Each worktree directory
//! gets its own bare Git repository for tracking changes independently.

use crate::service::CheckpointService;
use crate::store::CheckPointStore;
use error_mapping::*;
use pyo3::prelude::*;

/// Registers the `ShadowRepoManager` class with the Python module.
///
/// # Arguments
///
/// * `_` - The Python interpreter instance (unused)
/// * `m` - The Python module to register the class with
///
/// # Errors
///
/// Returns a `PyErr` if registration fails
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CheckPointStore>()?;
    m.add_class::<CheckpointService>()?;
    Ok(())
}
