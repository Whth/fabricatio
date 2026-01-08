use crate::store::{CheckPointStore, RepoEntry};
use crate::utils::{normalized_path_of, AsKey};
use error_mapping::AsPyErr;
use fabricatio_logger::debug;
use git2::Repository;
use moka::sync::Cache;
use pyo3::{pyclass, pymethods, PyResult};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};

use rayon::prelude::*;
use std::fs;
use std::fs::read_dir;
use std::path::PathBuf;
use utils::mwrap;


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

#[gen_stub_pyclass]
#[pyclass]
pub struct CheckpointService {
    stores_root: PathBuf,
    repo_cache: Cache<PathBuf, RepoEntry>,
}

impl CheckpointService {
    fn create_from_path(&self, workspace: PathBuf, repo_root: PathBuf) -> PyResult<CheckPointStore> {
        debug!(
                    "Creating repo for {} at {}",
                    workspace.display(),
                    repo_root.display()
                );
        let repo = self.repo_cache.try_get_with(
            repo_root.clone(),
            || {
                Ok(mwrap(Repository::init_bare(&repo_root)?))
            },
        ).into_pyresult()?;

        let store = CheckPointStore::new(workspace, repo);
        store.configure()?.add_init_commit()?;
        Ok(store)
    }


    fn open_from_path(&self, workspace: PathBuf, repo_root: PathBuf) -> PyResult<CheckPointStore> {
        debug!(
            "Opening repo for {} at {}",
            workspace.display(),
            repo_root.display()
        );
        let repo = self.repo_cache.try_get_with(
            repo_root.clone(),
            || {
                Ok(mwrap(Repository::open(repo_root)?))
            },
        ).into_pyresult()?;
        let store = CheckPointStore::new(workspace, repo);
        Ok(store)
    }

    fn create_or_open(&self, workspace: PathBuf, repo_root: PathBuf) -> PyResult<CheckPointStore> {
        if repo_root.exists() {
            self.open_from_path(workspace, repo_root)
        } else {
            self.create_from_path(workspace, repo_root)
        }
    }


    #[inline]
    fn repo_root_of(&self, workspace: PathBuf) -> PathBuf {
        self.stores_root.join(workspace.as_key())
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl CheckpointService {
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
    fn get_store(&self, worktree_dir: PathBuf) -> PyResult<CheckPointStore> {
        let worktree_dir = normalized_path_of(worktree_dir)?;
        self.create_or_open(worktree_dir.clone(), self.repo_root_of(worktree_dir))
    }
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
    #[pyo3(signature = (stores_root, cache_size=10))]
    fn new(stores_root: PathBuf, cache_size: u64) -> PyResult<Self> {
        fs::create_dir_all(&stores_root).into_pyresult()?;
        Ok(Self {
            stores_root: stores_root.canonicalize().into_pyresult()?,
            repo_cache: Cache::new(cache_size),
        })
    }


    fn workspaces(&self) -> PyResult<Vec<PathBuf>> {
        Ok(read_dir(&self.stores_root)
            .into_pyresult()?
            .par_bridge()
            .filter_map(Result::ok)
            .filter(|entry| entry.file_type().is_ok_and(|ft| ft.is_dir()))
            .map(|entry| entry.path())
            .filter_map(|entry| Repository::open(entry).ok())
            .filter_map(|repo| repo.workdir().map(|p| p.to_path_buf()))
            .collect::<Vec<_>>())
    }
}