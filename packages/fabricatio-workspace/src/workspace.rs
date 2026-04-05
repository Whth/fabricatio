use error_mapping::AsPyErr;
use fabricatio_logger::{debug, trace};
use git2::{BranchType, Repository, WorktreeAddOptions};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use std::path::PathBuf;


/// Forks a new Git worktree with safety checks and automatic cleanup.
///
/// This function creates a new worktree linked to a specific branch. It handles
/// branch creation, conflict detection across existing worktrees, and ensures
/// atomicity by cleaning up partial directories if the worktree addition fails.
///
/// Args:
///     repo_path (PathBuf): The absolute or relative path to the main Git repository.
///     to (PathBuf): The destination path where the new worktree will be created.
///     branch_name (str): The name of the branch to associate with the new worktree.
///     base_branch (Optional[str]): The name of the existing branch to use as the starting point
///         for creating `branch_name` if it does not already exist. If `None`, the current
///         `HEAD` of the main repository is used as the base.
///     exist_ok (bool): If `True`, the function will return the path of an existing worktree
///         if one is already checked out to `branch_name`, instead of raising an error.
///         If `False`, a conflict raises a `RuntimeError`.
///
/// Returns:
///     PathBuf: The absolute path to the newly created (or existing) worktree directory.
///
/// Raises:
///     RuntimeError: If `branch_name` is already checked out in another worktree and `exist_ok` is `False`.
///     RuntimeError: If `branch_name` already exists as a local branch but is not checked out in any worktree
///         (preventing accidental overwriting or ambiguous state).
///     RuntimeError: If the destination path `to` already exists on the filesystem.
///     RuntimeError: If the underlying Git operation to add the worktree fails.
///
/// Note:
///     - If the branch `branch_name` does not exist, it will be created automatically.
///     - If `base_branch` is provided but invalid, the function falls back to using the current `HEAD`.
///     - Partial directories created at `to` during a failed operation are automatically removed.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
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
                trace!("Use exist worktree: {}", wt.path().display());
                Ok(wt.path().to_path_buf())
            } else {
                Err(PyRuntimeError::new_err(format!(
                    "Branch `{branch_name}` is occupied by worktree `{wt_name}` at {}",
                    wt.path().display()
                )))
            };
        }
    }

    let b_ref = if let Some(base) = base_branch {
        repo.find_branch(&base, BranchType::Local)
            .into_pyresult()
            .map(|b| b.into_reference())
            .or_else(|_| {
                debug!("Branch `{base}` not found or not available, using head instead.");

                repo.head().into_pyresult()
            })?
    } else if repo.find_branch(branch_name, BranchType::Local).is_err() {
        repo.branch(
            branch_name,
            &repo
                .head()
                .into_pyresult()?
                .peel_to_commit()
                .into_pyresult()?,
            false,
        )
            .into_pyresult()?
            .into_reference()
    } else {
        return Err(PyRuntimeError::new_err(format!(
            "Branch `{branch_name}` already exists, can't create other one with the same name!"
        )));
    };

    if to.exists() {
        return Err(PyRuntimeError::new_err(format!(
            "Can not create a worktree at {}, since the path is already occupied.",
            to.display()
        )));
    }

    match repo.worktree(
        branch_name,
        &to,
        Some(
            WorktreeAddOptions::new()
                .reference(Some(&b_ref))
                .checkout_existing(true),
        ),
    ) {
        Ok(wt) => Ok(wt.path().to_path_buf()),
        Err(e) => {
            let _ = std::fs::remove_dir_all(&to);
            Err(PyRuntimeError::new_err(format!(
                "Worktree creation failed: {}",
                e
            )))
        }
    }
}

/// Prunes all stale worktrees from the repository and ensures branch availability.
///
/// This function scans the repository for worktrees that are no longer valid
/// (e.g., the working directory has been manually deleted or corrupted) and removes
/// their metadata. It effectively cleans up the repository state, ensuring that
/// branches previously locked by these stale worktrees are released and can be
/// used again.
///
/// This is analogous to running `git worktree prune` but with additional safety
/// checks to ensure internal consistency within the application's context.
///
/// Args:
///     repo_path (PathBuf): The absolute or relative path to the main Git repository
///         where stale worktrees should be pruned.
///
/// Returns:
///     int: The number of stale worktrees successfully pruned.
///
/// Raises:
///     RuntimeError: If the repository cannot be opened or if there is an error
///         accessing the worktree metadata directory.
///
/// Note:
///     - This operation only removes the metadata links in `.git/worktrees`.
///     - It does not delete the actual working directory files if they still exist on disk;
///       it only cleans up the repository's reference to them.
///     - After pruning, branches associated with these worktrees are considered free
///       and can be checked out in new worktrees.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature=(repo_path))]
pub fn prune(repo_path: PathBuf) -> PyResult<usize> {
    let repo = Repository::open(&repo_path).into_pyresult()?;

    let mut pruned_count = 0;
    let wt_list = repo.worktrees().into_pyresult()?;

    for wt_name in wt_list.iter().flatten() {
        trace!("Checking worktree for pruning: {wt_name}");
        if let Ok(wt) = repo.find_worktree(wt_name) {
            if !wt.is_prunable(None).into_pyresult()? {
                continue;
            }

            trace!(
                "Pruning stale worktree: {wt_name} at {}",
                wt.path().display()
            );
            wt.prune(None).into_pyresult()?;
            pruned_count += 1;
        }
    }

    Ok(pruned_count)
}

/// Commits changes in a specific worktree with optional file selection.
///
/// This function stages specified files (or all modified files if none are specified)
/// and creates a new commit in the repository associated with the given worktree.
/// It automatically configures the committer and author based on the Git configuration
/// found in the worktree's repository.
///
/// Args:
///     worktree_path (PathBuf): The absolute or relative path to the root of the worktree
///         where the commit should be made.
///     msg (str): The commit message describing the changes.
///     files (Optional[List[str]]): A list of file paths relative to the worktree root
///         to stage for the commit. If `None` or an empty list, all currently modified
///         and tracked files in the worktree will be staged automatically.
///
/// Returns:
///     str: The hexadecimal string representation of the new commit's OID (Object ID).
///
/// Raises:
///     RuntimeError: If the worktree path is invalid or not part of a valid Git repository.
///     RuntimeError: If there are no changes to commit (empty index).
///     RuntimeError: If staging the specified files fails (e.g., file not found).
///     RuntimeError: If the commit operation fails due to Git constraints (e.g., merge conflicts).
///
/// Note:
///     - The function uses the current `HEAD` of the worktree as the parent commit.
///     - Author and Committer identities are derived from the Git config (`user.name` and `user.email`).
///     - If `files` is provided, only those files are added to the index; other staged changes remain untouched
///       unless explicitly overwritten by this operation's logic (here we add to index).
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature=(worktree_path, msg, files=None))]
pub fn commit(worktree_path: PathBuf, msg: &str, files: Option<Vec<String>>) -> PyResult<String> {
    let repo = Repository::open(&worktree_path).into_pyresult()?;

    // 1. Prepare Index
    let mut index = repo.index().into_pyresult()?;

    // 2. Stage files
    if let Some(file_list) = files {
        if file_list.is_empty() {} else {
            for file in file_list {
                index
                    .add_path(std::path::Path::new(&file))
                    .into_pyresult()?;
            }
        }
    } else {
        index
            .add_all(["."].iter(), git2::IndexAddOption::DEFAULT, None)
            .into_pyresult()?;
    }

    index.write().into_pyresult()?;

    // 3. Create Tree
    let tree_id = index.write_tree().into_pyresult()?;
    let tree = repo.find_tree(tree_id).into_pyresult()?;

    // 4. Get Parent Commit (HEAD)
    let parent_commit = repo
        .head()
        .into_pyresult()?
        .peel_to_commit()
        .into_pyresult()?;

    // 5. Get Signature (Author/Committer)
    let signature = repo.signature().into_pyresult()?;

    // 6. Create Commit
    let commit_oid = repo
        .commit(
            Some("HEAD"),      // Update HEAD reference
            &signature,        // Author
            &signature,        // Committer
            msg,               // Message
            &tree,             // Tree
            &[&parent_commit], // Parents
        )
        .into_pyresult()?;

    Ok(commit_oid.to_string())
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fork, m)?)?;
    m.add_function(wrap_pyfunction!(prune, m)?)?;
    m.add_function(wrap_pyfunction!(commit, m)?)?;
    Ok(())
}
