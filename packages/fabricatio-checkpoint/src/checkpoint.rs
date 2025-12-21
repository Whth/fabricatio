//! Shadow repository management for file checkpointing.
//!
//! This module provides a Python-accessible interface for managing shadow Git repositories
//! that track file changes and enable checkpoint/restore functionality. Each worktree directory
//! gets its own bare Git repository for tracking changes independently.

use blake3::hash;
use error_mapping::*;
use fabricatio_logger::*;
use git2::{Config, DiffOptions, IndexAddOption, Oid, Repository};
use moka::sync::Cache;
use pyo3::exceptions::PyOSError;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs;
use std::fs::read_dir;
use std::path::{Path, PathBuf, absolute};
use std::sync::{Arc, Mutex};
use utils::mwrap;
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

fn sanitize_path(root: &PathBuf, path: PathBuf) -> PyResult<PathBuf> {
    if path.is_relative() {
        Ok(path)
    } else {
        path.strip_prefix(root)
            .map(|p| p.to_path_buf())
            .map_err(|e| PyOSError::new_err(e.to_string()))
    }
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
            debug!("Found cached repo for {}", worktree_dir.display());
            Ok(repo)
        } else {
            let repo_path = self.shadow_root.join(worktree_dir.as_key());

            if read_dir(&repo_path).is_ok_and(|mut i| i.next().is_some()) {
                let repo = mwrap(Repository::open(&repo_path).into_pyresult()?);
                debug!(
                    "Opened repo for {} at {}",
                    worktree_dir.display(),
                    repo_path.display()
                );
                self.cache.insert(worktree_dir, repo.clone());
                Ok(repo)
            } else {
                let repo = Repository::init_bare(&repo_path).into_pyresult()?;

                // Configure the repository manually, since the git2-rs always try to put a `.git` file in the source, which pollutes the source directory.
                let mut config = repo.config().into_pyresult()?;
                Self::configure(&worktree_dir, &mut config)?;
                let repo = Repository::open(&repo_path).into_pyresult()?;
                debug!(
                    "Created repo for {} at {}",
                    worktree_dir.display(),
                    repo_path.display()
                );

                let tree_id = repo
                    .treebuilder(None)
                    .into_pyresult()?
                    .write()
                    .into_pyresult()?;
                {
                    let tree = repo.find_tree(tree_id).into_pyresult()?;

                    let sig = repo.signature().into_pyresult()?;
                    repo.commit(
                        Some("refs/heads/main"),
                        &sig,
                        &sig,
                        "Initial commit",
                        &tree,
                        &[],
                    )
                    .into_pyresult()?;
                }

                debug!("Add initial commit to {}", worktree_dir.display());
                let repo = mwrap(repo);
                self.cache.insert(worktree_dir, repo.clone());
                Ok(repo)
            }
        }
    }

    #[inline]
    /// Configures a newly created repository with essential settings.
    ///
    /// Sets up the repository configuration to work properly as a shadow repository,
    /// including disabling bare mode, enabling ref logging, setting the worktree path,
    /// and configuring default user identity.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory that this repository will track
    /// * `config` - Mutable reference to the repository's configuration object
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if any configuration operation fails
    fn configure(worktree_dir: &Path, config: &mut Config) -> Result<(), PyErr> {
        config.set_bool("core.bare", false).into_pyresult()?;
        config
            .set_bool("core.logallrefupdates", true)
            .into_pyresult()?;
        config
            .set_str("core.worktree", &worktree_dir.to_string_lossy())
            .into_pyresult()?;
        config.set_str("user.name", "Agent").into_pyresult()?;
        config
            .set_str("user.email", "placeholder@example.com")
            .into_pyresult()?;
        Ok(())
    }
}

#[pymethods]
impl ShadowRepoManager {
    /// Creates a new `ShadowRepoManager` instance.
    ///
    /// Initializes a shadow repository manager with the specified root directory
    /// and cache size. Creates the shadow root directory if it doesn't exist.
    ///
    /// # Arguments
    ///
    /// * `shadow_root` - The root directory where shadow repositories will be stored
    /// * `cache_size` - Maximum number of repositories to keep in the in-memory cache
    ///
    /// # Returns
    ///
    /// A new `ShadowRepoManager` instance
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if the shadow root directory cannot be created
    #[new]
    fn new(shadow_root: PathBuf, cache_size: u64) -> PyResult<Self> {
        fs::create_dir_all(&shadow_root).into_pyresult()?;
        Ok(Self {
            shadow_root: shadow_root.canonicalize().into_pyresult()?,
            cache: Cache::new(cache_size),
        })
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
    ///
    /// # Note
    ///
    /// If there are no changes to commit, this method returns the ID of the last commit (the HEAD).
    #[pyo3(signature=(worktree_dir, commit_msg=None))]
    pub fn save(&self, worktree_dir: PathBuf, commit_msg: Option<String>) -> PyResult<String> {
        let worktree_dir = absolute(worktree_dir).into_pyresult()?;
        let repo_entry = self.get_repo(worktree_dir)?;
        let repo = repo_entry.lock().into_pyresult()?;
        let mut index = repo.index().into_pyresult()?;
        let sig = repo.signature().into_pyresult()?;
        index.update_all(["*"].iter(), None).into_pyresult()?;
        index
            .add_all(["*"].iter(), IndexAddOption::default(), None)
            .into_pyresult()?;

        let head_commit = repo
            .head()
            .into_pyresult()?
            .peel_to_commit()
            .into_pyresult()?;
        let tree = {
            let tree_id = index.write_tree().into_pyresult()?;
            repo.find_tree(tree_id).into_pyresult()?
        };

        if tree.id() == head_commit.tree_id() {
            debug!("No changes to commit, returning head commit...");
            Ok(head_commit.id().to_string())
        } else {
            repo.commit(
                Some("HEAD"),
                &sig,
                &sig,
                commit_msg.unwrap_or_default().as_str(),
                &tree,
                &[&head_commit],
            )
            .into_pyresult()
            .map(|oid| oid.to_string())
        }
    }
    /// Drops the shadow repository for the given worktree directory.
    ///
    /// This method removes the shadow repository from both the file system and the cache.
    /// It deletes the entire repository directory and removes the cache entry.
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory whose shadow repository should be dropped
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if:
    /// - The shadow repository directory cannot be removed from the file system
    pub fn drop(&self, worktree_dir: PathBuf) -> PyResult<()> {
        let worktree_dir = absolute(worktree_dir).into_pyresult()?;
        let repo_path = self.shadow_root.join(worktree_dir.as_key());
        if !repo_path.exists() {
            return Ok(());
        }
        fs::remove_dir_all(&repo_path).into_pyresult()?;
        self.cache.remove(&worktree_dir);
        Ok(())
    }
    /// Lists all commit IDs in the shadow repository's history.
    ///
    /// This method retrieves the complete commit history from the current HEAD
    /// backwards through the parent commits. The commits are returned in reverse
    /// chronological order (newest first).
    ///
    /// # Arguments
    ///
    /// * `worktree_dir` - The worktree directory whose commit history to retrieve
    ///
    /// # Returns
    ///
    /// A vector of commit IDs (OIDs as strings) in reverse chronological order
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if:
    /// - The shadow repository is not found
    /// - Git operations fail while walking the commit history
    pub fn commits(&self, worktree_dir: PathBuf) -> PyResult<Vec<String>> {
        let worktree_dir = absolute(worktree_dir).into_pyresult()?;
        let repo_entry = self.get_repo(worktree_dir)?;
        let repo = repo_entry.lock().into_pyresult()?;
        let mut revwk = repo.revwalk().into_pyresult()?;
        revwk.push_head().into_pyresult()?;
        Ok(revwk
            .filter_map(Result::ok)
            .map(|oid| oid.to_string())
            .skip(1) // skip the Initial commit which is a placeholder
            .collect())
    }

    /// Lists all workspaces managed by this shadow repository manager.
    ///
    /// This method returns a list of worktree directories that have associated
    /// shadow repositories. When `cached_only` is true, it returns only the
    /// workspaces currently in the in-memory cache. When false, it scans the
    /// filesystem to discover all existing shadow repositories.
    ///
    /// # Arguments
    ///
    /// * `cached_only` - If true, return only cached workspaces; if false, scan filesystem
    ///
    /// # Returns
    ///
    /// A vector of worktree directory paths
    ///
    /// # Errors
    ///
    /// Returns a `PyErr` if filesystem operations fail during scanning
    #[pyo3(signature=(cached_only=true))]
    pub fn workspaces(&self, cached_only: bool) -> PyResult<Vec<PathBuf>> {
        if cached_only {
            debug!("Returning cached workspaces...");
            Ok(self
                .cache
                .iter()
                .map(|(k, _)| k.to_path_buf())
                .collect::<Vec<_>>())
        } else {
            Ok(read_dir(&self.shadow_root)
                .into_pyresult()?
                .par_bridge()
                .filter_map(Result::ok)
                .filter(|entry| entry.file_type().is_ok_and(|ft| ft.is_dir()))
                .map(|entry| entry.path().to_path_buf())
                .filter_map(|entry| Repository::open(entry).ok())
                .filter_map(|repo| repo.workdir().map(|p| p.to_path_buf()))
                .collect::<Vec<_>>())
        }
    }

    /// Resets the worktree to a specific commit.
    ///
    /// Performs a hard reset of the worktree directory to match the state at the specified commit.
    /// This discards all changes in the working directory and index, making them match the commit.
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
        let worktree_dir = absolute(worktree_dir).into_pyresult()?;

        let repo_entry = self.get_repo(worktree_dir)?;
        let repo = repo_entry.lock().into_pyresult()?;
        let commit = repo
            .find_commit(Oid::from_str(&commit_id).into_pyresult()?)
            .into_pyresult()?;
        repo.reset(&commit.into_object(), git2::ResetType::Hard, None)
            .into_pyresult()
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
        file_path: PathBuf,
    ) -> PyResult<()> {
        let worktree_dir = absolute(worktree_dir).into_pyresult()?;

        let file_path = sanitize_path(&worktree_dir, file_path)?;
        let repo_entry = self.get_repo(worktree_dir.clone())?;
        let repo = repo_entry.lock().into_pyresult()?;
        let commit = repo
            .find_commit(Oid::from_str(&commit_id).into_pyresult()?)
            .into_pyresult()?;

        debug!(
            "Rolling back file {} to commit {}",
            file_path.display(),
            commit_id
        );
        let file_obj = commit
            .tree()
            .into_pyresult()?
            .get_path(&file_path)
            .into_pyresult()?;

        let blob = repo.find_blob(file_obj.id()).into_pyresult()?;
        fs::write(worktree_dir.join(file_path), blob.content()).into_pyresult()
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
        file_path: PathBuf,
    ) -> PyResult<String> {
        let worktree_dir = absolute(worktree_dir).into_pyresult()?;

        let file_path = sanitize_path(&worktree_dir, file_path)?;
        let repo_entry = self.get_repo(worktree_dir)?;
        let repo = repo_entry.lock().into_pyresult()?;
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
