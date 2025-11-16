//! Shadow repository management for file checkpointing.
//!
//! This module provides a Python-accessible interface for managing shadow Git repositories
//! that track file changes and enable checkpoint/restore functionality. Each worktree directory
//! gets its own bare Git repository for tracking changes independently.

use blake3::hash;
use git2::{DiffOptions, IndexAddOption, Oid, Repository};
use moka::sync::Cache;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::path::PathBuf;
use std::sync::{Arc, LockResult, Mutex};

/// Trait for converting types into cache-friendly string keys.
trait AsKey {
    /// Converts the implementing type into a unique string key.
    fn as_key(&self) -> String;
}

impl AsKey for PathBuf {
    /// Generates a unique key from a path by combining the filename with a hash prefix.
    ///
    /// Creates a key in the format `filename_hash8` where `hash8` is the first 8 characters
    /// of the BLAKE3 hash of the full path. This ensures uniqueness while maintaining
    /// human-readable filenames.
    fn as_key(&self) -> String {
        let hash = &hash(self.to_string_lossy().as_bytes()).to_string()[..8];
        format!(
            "{}_{hash}",
            self.file_name().unwrap_or_default().to_string_lossy()
        )
    }
}

/// Thread-safe reference to a Git repository.
///
/// Wraps a Git repository in an `Arc<Mutex<>>` to allow safe concurrent access
/// from multiple threads while maintaining interior mutability.
type RepoEntry = Arc<Mutex<Repository>>;

/// Wraps a Git repository in a thread-safe container.
///
/// # Arguments
///
/// * `repo` - The Git repository to wrap
///
/// # Returns
///
/// An `Arc<Mutex<Repository>>` that can be safely shared across threads.
#[inline]
fn wrap(repo: Repository) -> RepoEntry {
    Arc::new(Mutex::new(repo))
}
/// Manages shadow Git repositories for file checkpointing.
///
/// A shadow repository manager creates and maintains separate bare Git repositories
/// for each worktree directory. This enables independent version control and checkpointing
/// without interfering with any existing Git repositories in the worktree.
///
/// # Fields
///
/// * `shadow_root` - Root directory where all shadow repositories are stored
/// * `cache` - In-memory cache of repository instances to avoid repeated disk access
#[pyclass]
struct ShadowRepoManager {
    shadow_root: PathBuf,
    cache: Cache<PathBuf, RepoEntry>,
}

/// Trait for converting various error types to PyO3 results.
///
/// Provides a uniform interface for converting Git and synchronization errors
/// into Python exceptions that can be propagated across the FFI boundary.
trait AsPyErr<T> {
    /// Converts the implementing type into a `PyResult`.
    fn into_pyresult(self) -> PyResult<T>;
}

impl<T> AsPyErr<T> for Result<T, git2::Error> {
    /// Converts a `git2::Error` into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

impl<T> AsPyErr<T> for LockResult<T> {
    /// Converts a poisoned lock error into a Python `RuntimeError`.
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

impl ShadowRepoManager {
    /// Gets or creates a shadow repository for the given worktree directory.
    ///
    /// This method first checks the cache for an existing repository. If not found,
    /// it either opens an existing bare repository from disk or creates a new one.
    /// For new repositories, it also creates a Git worktree linked to the target directory.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The directory to be tracked by the shadow repository
    ///
    /// # Returns
    ///
    /// A thread-safe reference to the Git repository
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if repository operations fail
    fn get_repo(&self, worktree_dir: PathBuf) -> PyResult<RepoEntry> {
        if let Some(repo) = self.cache.get(&worktree_dir) {
            Ok(repo)
        } else {
            let repo_path = self.shadow_root.join(worktree_dir.as_key());

            if repo_path.exists() {
                let repo = wrap(Repository::open(repo_path).into_pyresult()?);
                self.cache.insert(worktree_dir, repo.clone());
                Ok(repo)
            } else {
                let repo = wrap(Repository::init_bare(repo_path.clone()).into_pyresult()?);

                repo.lock()
                    .into_pyresult()?
                    .worktree(
                        &worktree_dir.to_string_lossy(),
                        worktree_dir.as_path(),
                        None,
                    )
                    .into_pyresult()?;
                self.cache.insert(worktree_dir, repo.clone());
                Ok(repo)
            }
        }
    }
}

#[pymethods]
impl ShadowRepoManager {
    /// Creates a new `ShadowRepoManager` instance.
    ///
    /// # Arguments
    ///
    /// * `shadow_root` - Root directory where shadow repositories will be stored
    /// * `cache_size` - Maximum number of repositories to keep in the cache
    ///
    /// # Returns
    ///
    /// A new `ShadowRepoManager` instance
    #[new]
    fn new(shadow_root: PathBuf, cache_size: u64) -> Self {
        Self {
            shadow_root,
            cache: Cache::new(cache_size),
        }
    }
    /// Saves the current state of the worktree as a new commit.
    ///
    /// This method stages all changes in the worktree directory and creates a new commit
    /// in the shadow repository. It acts as a checkpoint that can later be restored.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory to checkpoint
    /// * `commit_msg` - Optional commit message; defaults to empty string if not provided
    ///
    /// # Returns
    ///
    /// The commit ID (OID) as a string
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if:
    /// - The shadow repository is not found
    /// - Git operations fail (staging, committing, etc.)
    pub fn save(&self, worktree_dir: PathBuf, commit_msg: Option<String>) -> PyResult<String> {
        if let Ok(repo_entry) = self.get_repo(worktree_dir)
            && let Ok(repo) = repo_entry.lock()
            && let Ok(index) = repo.index().as_mut()
        {
            let sig = repo.signature().into_pyresult()?;
            index.update_all(["*"].iter(), None).into_pyresult()?;
            index
                .add_all(["*"].iter(), IndexAddOption::default(), None)
                .into_pyresult()?;

            let tree = {
                let tree_id = index.write_tree().into_pyresult()?;
                repo.find_tree(tree_id).into_pyresult()?
            };

            let parent: Vec<_> = if let Ok(commit) = repo.head().into_pyresult()?.peel_to_commit() {
                vec![commit]
            } else {
                vec![]
            };

            repo.commit(
                Some("HEAD"),
                &sig,
                &sig,
                commit_msg.unwrap_or_default().as_str(),
                &tree,
                &parent.iter().collect::<Vec<_>>(),
            )
            .into_pyresult()
            .map(|oid| oid.to_string())
        } else {
            Err(PyRuntimeError::new_err("Shadow repo not found".to_string()))
        }
    }

    /// Resets the worktree to a specific commit state.
    ///
    /// This performs a mixed reset, updating the index but leaving the working directory unchanged.
    /// Similar to `git reset --mixed <commit_id>`.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory to reset
    /// * `commit_id` - The commit ID (OID as string) to reset to
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if:
    /// - The shadow repository is not found
    /// - The commit ID is invalid
    /// - The reset operation fails
    pub fn reset(&self, worktree_dir: PathBuf, commit_id: String) -> PyResult<()> {
        if let Ok(repo) = self.get_repo(worktree_dir)
            && let Ok(repo) = repo.lock()
        {
            let commit = repo
                .find_commit(Oid::from_str(&commit_id).into_pyresult()?)
                .into_pyresult()?;
            repo.reset(&commit.into_object(), git2::ResetType::Mixed, None)
                .into_pyresult()
        } else {
            Err(PyRuntimeError::new_err("Shadow repo not found".to_string()))
        }
    }

    /// Restores a specific file from a commit.
    ///
    /// This rolls back a single file to its state at the specified commit,
    /// checking out that file from the commit's tree.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory containing the file
    /// * `commit_id` - The commit ID (OID as string) to restore from
    /// * `file_path` - The relative path to the file within the worktree
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if:
    /// - The shadow repository is not found
    /// - The commit ID is invalid
    /// - The file is not found in the commit
    /// - The checkout operation fails
    pub fn rollback(
        &self,
        worktree_dir: PathBuf,
        commit_id: String,
        file_path: String,
    ) -> PyResult<()> {
        if let Ok(repo) = self.get_repo(worktree_dir)
            && let Ok(repo) = repo.lock()
        {
            let commit = repo
                .find_commit(Oid::from_str(&commit_id).into_pyresult()?)
                .into_pyresult()?;

            let file_obj = commit
                .tree()
                .into_pyresult()?
                .get_name(&file_path)
                .ok_or_else(|| PyRuntimeError::new_err("file not found"))?
                .to_object(&repo)
                .into_pyresult()?;

            repo.checkout_tree(&file_obj, None).into_pyresult()
        } else {
            Err(PyRuntimeError::new_err("Shadow repo not found".to_string()))
        }
    }

    /// Retrieves the diff for a specific file at a given commit.
    ///
    /// Compares the file state at the specified commit with its state in the parent commit,
    /// returning a patch-format diff string. If the commit has no parent (initial commit),
    /// it compares against an empty tree.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory containing the file
    /// * `commit_id` - The commit ID (OID as string) to get the diff from
    /// * `file_path` - The relative path to the file within the worktree
    ///
    /// # Returns
    ///
    /// A string containing the unified diff in patch format
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if:
    /// - The shadow repository is not found
    /// - The commit ID is invalid
    /// - Git diff operations fail
    pub fn get_file_diff(
        &self,
        worktree_dir: PathBuf,
        commit_id: String,
        file_path: String,
    ) -> PyResult<String> {
        if let Ok(repo) = self.get_repo(worktree_dir)
            && let Ok(repo) = repo.lock()
        {
            let commit = repo
                .find_commit(Oid::from_str(&commit_id).into_pyresult()?)
                .into_pyresult()?;

            let file_obj = commit.tree().into_pyresult()?;

            let parent_tree_obj = if let Ok(parent) = commit.parent(0).as_ref() {
                parent.tree().into_pyresult()?
            } else {
                let id = repo
                    .treebuilder(None)
                    .into_pyresult()?
                    .write()
                    .into_pyresult()?;
                repo.find_tree(id).into_pyresult()?
            };

            let mut opts = DiffOptions::new();
            opts.pathspec(&file_path);

            let diff = repo
                .diff_tree_to_tree(Some(&parent_tree_obj), Some(&file_obj), Some(&mut opts))
                .into_pyresult()?;
            let mut ret = String::new();

            diff.print(git2::DiffFormat::Patch, |_delta, _hunk, line| {
                ret.push_str(std::str::from_utf8(line.content()).unwrap_or("<invalid utf8>"));
                true
            })
            .into_pyresult()?;

            Ok(ret)
        } else {
            Err(PyRuntimeError::new_err("Shadow repo not found".to_string()))
        }
    }
}

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
    m.add_class::<ShadowRepoManager>()?;
    Ok(())
}
