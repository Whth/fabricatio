use blake3::hash;
use error_mapping::AsPyErr;
use fabricatio_logger::trace;
use git2::{Commit, Repository};
use pyo3::prelude::*;
use pyo3::{Bound, PyResult, Python};
use std::fs;
use std::fs::read_dir;
use std::path::{Path, PathBuf, absolute};
use std::sync::MutexGuard;

use rayon::prelude::*;

#[inline]
pub(crate) fn head_commit_of<'a>(repo: &'a MutexGuard<'a, Repository>) -> PyResult<Commit<'a>> {
    repo.head()
        .into_pyresult()?
        .peel_to_commit()
        .into_pyresult()
}

pub(crate) fn normalized_path_of<P: AsRef<Path>>(path: P) -> PyResult<PathBuf> {
    absolute(path).into_pyresult()
}

pub(crate) fn normalized_rel_path(root: &PathBuf, path: PathBuf) -> PyResult<PathBuf> {
    if path.is_relative() {
        Ok(path)
    } else {
        path.strip_prefix(root)
            .map(|p| p.to_path_buf())
            .into_pyresult()
    }
}

/// Creates a shadow repository by initializing a bare repository and then configuring it
/// to act as a regular repository with the specified workspace as its working directory.
///
/// This function:
/// 1. Initializes a bare repository at the given `repo_root`
/// 2. Configures it to be non-bare (`core.bare = false`)
/// 3. Sets up logging of all ref updates (`core.logallrefupdates = true`)
/// 4. Sets the working directory to the provided workspace (`core.worktree`)
/// 5. Sets dummy user information for commits
/// 6. Re-opens the repository to apply the configuration changes
pub(crate) fn create_shadow_repo(
    workspace: &Path,
    repo_root: &PathBuf,
) -> Result<Repository, git2::Error> {
    let repo = Repository::init_bare(repo_root)?;

    let mut config = repo.config()?;
    config.set_bool("core.bare", false)?;
    config.set_bool("core.logallrefupdates", true)?;
    config.set_str("core.worktree", &workspace.to_string_lossy())?;
    config.set_str("user.name", "Agent")?;
    config.set_str("user.email", "placeholder@example.com")?;
    trace!("Configured repository...");
    Repository::open(repo_root)
}

/// Trait for converting types into cache-friendly string keys.
pub(crate) trait AsKey {
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

macro_rules! dir_entries {
    ($path:expr) => {
        read_dir($path)
            .into_pyresult()?
            .par_bridge()
            .filter_map(Result::ok)
            .filter(|entry| entry.file_type().is_ok_and(|ft| ft.is_dir()))
            .map(|entry| entry.path())
    };
}

pub(crate) fn managed_workspaces(stores_root: &PathBuf) -> PyResult<Vec<PathBuf>> {
    Ok(dir_entries!(stores_root)
        .filter_map(|entry| Repository::open(entry).ok())
        .filter_map(|repo| repo.workdir().map(|p| p.to_path_buf()))
        .collect::<Vec<_>>())
}

/// Removes all store repositories under the given root path whose working directories no longer exist.
///
/// This function:
/// 1. Iterates through all directories under the stores_root
/// 2. Attempts to open each as a git repository
/// 3. Checks if the repository's working directory still exists
/// 4. If the working directory doesn't exist, removes the entire repository directory
///
/// This is used to clean up shadow repositories whose original workspaces have been deleted.
#[pyfunction]
pub(crate) fn prune_stores(stores_root: PathBuf) -> PyResult<()> {
    dir_entries!(stores_root)
        .filter_map(|entry| Repository::open(&entry).ok().map(|repo| (entry, repo)))
        .filter_map(|(entry, repo)| {
            repo.workdir()
                .map(|p| p.to_path_buf().exists().then_some(entry))?
        })
        .try_for_each(fs::remove_dir_all)?;

    Ok(())
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(prune_stores, m)?)?;
    Ok(())
}
