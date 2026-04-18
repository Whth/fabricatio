//! Shadow repository management for file checkpointing.
//!
//! This module provides a Python-accessible interface for managing shadow Git repositories
//! that track file changes and enable checkpoint/restore functionality. Each worktree directory
//! gets its own bare Git repository for tracking changes independently.

use crate::service::CheckpointService;
use crate::store::CheckPointStore;
use error_mapping::*;
use pyo3::prelude::*;

/// Registers the CheckpointService and CheckPointStore classes with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CheckPointStore>()?;
    m.add_class::<CheckpointService>()?;
    Ok(())
}
