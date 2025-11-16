use blake3::hash;
use git2::{DiffOptions, IndexAddOption, Oid, Repository};
use moka::sync::Cache;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::path::PathBuf;
use std::sync::{Arc, LockResult, Mutex};

trait AsKey {
    fn as_key(&self) -> String;
}

impl AsKey for PathBuf {
    fn as_key(&self) -> String {
        let hash = &hash(self.to_string_lossy().as_bytes()).to_string()[..8];
        format!(
            "{}_{hash}",
            self.file_name().unwrap_or_default().to_string_lossy()
        )
    }
}

type RepoEntry = Arc<Mutex<Repository>>;

#[inline]
fn wrap(repo: Repository) -> RepoEntry {
    Arc::new(Mutex::new(repo))
}
#[pyclass]
struct ShadowRepoManager {
    shadow_root: PathBuf,
    cache: Cache<PathBuf, RepoEntry>,
}

trait AsPyErr<T> {
    fn into_pyresult(self) -> PyResult<T>;
}

impl<T> AsPyErr<T> for Result<T, git2::Error> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

impl<T> AsPyErr<T> for LockResult<T> {
    fn into_pyresult(self) -> PyResult<T> {
        self.map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
}

impl ShadowRepoManager {
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
    #[new]
    fn new(shadow_root: PathBuf, cache_size: u64) -> Self {
        Self {
            shadow_root,
            cache: Cache::new(cache_size),
        }
    }
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

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ShadowRepoManager>()?;
    Ok(())
}
