use error_mapping::AsPyErr;
use git2::{Reference, Repository, WorktreeAddOptions};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::path::PathBuf;

#[gen_stub_pyfunction]
#[pyfunction]
pub fn fork(
    repo_path: PathBuf,
    to: PathBuf,
    branch_name: &str,
    base_branch: Option<String>,
) -> PyResult<()> {
    let repo = Repository::open(repo_path).into_pyresult()?;

    repo.worktree(branch_name, to.as_path(), None)
        .into_pyresult()?;

    Ok(())
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fork, m)?)?;
    Ok(())
}
