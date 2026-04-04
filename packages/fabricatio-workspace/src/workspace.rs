use error_mapping::AsPyErr;
use fabricatio_logger::{debug, trace};
use git2::{BranchType, Repository, WorktreeAddOptions};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::gen_stub_pyfunction;
use std::path::PathBuf;

///
/// Safely forks a new worktree.
/// 1. Pre-checks branch conflicts and path existence.
/// 2. Creates branch if missing.
/// 3. Adds worktree with cleanup on failure.
#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature=(repo_path, to, branch_name, base_branch=None, exist_ok=false))]
pub fn fork(
    repo_path: PathBuf,
    to: PathBuf,
    branch_name: &str,
    base_branch: Option<String>,
    exist_ok: bool,
) -> PyResult<PathBuf> {
    let repo = Repository::open(&repo_path).into_pyresult()?;

    // --- Phase 1: Pre-checks (No side effects) ---

    // 1. Check for branch conflicts in existing worktrees

    let wt_list = repo.worktrees().into_pyresult()?;


    for wt_name in wt_list.iter().flatten() {
        trace!("Looking worktree: {wt_name}");
        if let Ok(wt) = repo.find_worktree(wt_name)
            && let Ok(repo) = Repository::open(wt.path())
            && let Ok(head) = repo.head()
            && let Some(ref_name) = head.name()
            && ref_name.ends_with(branch_name)
        {
            return if exist_ok {
                trace!("Use exist worktree: {}",wt.path().display());
                Ok(wt.path().to_path_buf())
            } else {
                Err(PyRuntimeError::new_err(
                    format!("Branch `{branch_name}` is occupied by worktree `{wt_name}` at {}", wt.path().display())
                ))
            };
        }
    }


    // 3. Ensure branch exists
    let b_ref = if let Some(base) = base_branch {
        repo.find_branch(&base, BranchType::Local).into_pyresult().map(|b| b.into_reference()).or_else(
            |_| {
                debug!("Branch `{base}` not found or not available, using head instead.");

                repo.head().into_pyresult()
            }
        )?
    } else if repo.find_branch(branch_name, BranchType::Local).is_err() {
        repo
            .branch(branch_name, &repo.head().into_pyresult()?.peel_to_commit().into_pyresult()?, false)
            .into_pyresult()?
            .into_reference()
    } else {
        return Err(
            PyRuntimeError::new_err(
                format!("Branch `{branch_name}` already exists, can't create other one with the same name!")
            )
        )
    };

    // --- Phase 2: Execute with Rollback ---

    if to.exists() {
        return Err(PyRuntimeError::new_err(
            format!("Can not create a worktree at {}, since the path is already occupied.", to.display())
        ));
    }


    match repo.worktree(branch_name, &to, Some(WorktreeAddOptions::new().reference(Some(&b_ref)).checkout_existing(true))) {
        Ok(wt) => Ok(wt.path().to_path_buf()),
        Err(e) => {
            let _ = std::fs::remove_dir_all(&to); // Cleanup partial state
            Err(PyRuntimeError::new_err(format!("Worktree creation failed: {}", e)))
        }
    }
}
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fork, m)?)?;
    Ok(())
}
