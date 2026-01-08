use crate::constants::HEAD_REF_NAME;
use crate::utils::normalized_rel_path;
use error_mapping::AsPyErr;
use fabricatio_logger::*;
use git2::{DiffOptions, IndexAddOption, Oid, Repository};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, MutexGuard};

pub type RepoEntry = Arc<Mutex<Repository>>;


#[gen_stub_pyclass]
#[pyclass]
pub struct CheckPointStore {
    /// The workspace directory where the checkpoints are stored for
    #[pyo3(get)]
    workspace: PathBuf,
    repo: RepoEntry,
}


impl CheckPointStore {
    pub(crate) fn new(workspace: PathBuf, repo: RepoEntry) -> Self {
        Self {
            workspace,
            repo,
        }
    }

    #[inline]
    pub(crate) fn add_init_commit(&self) -> Result<&Self, PyErr> {
        let repo = self.access_repo()?;

        let tree_id = repo
            .treebuilder(None)
            .into_pyresult()?
            .write()
            .into_pyresult()?;
        {
            let tree = repo.find_tree(tree_id).into_pyresult()?;

            let sig = repo.signature().into_pyresult()?;
            repo.commit(
                Some(HEAD_REF_NAME),
                &sig,
                &sig,
                "Initial commit",
                &tree,
                &[],
            )
                .into_pyresult()?;
        };
        Ok(self)
    }

    #[inline]
    /// Configure the repository manually, since the git2-rs always try to put a `.git`
    /// file in the source, which pollutes the source directory.
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
    pub(crate) fn configure(&self) -> Result<&Self, PyErr> {
        let mut config = self.access_repo()?.config().into_pyresult()?;
        config.set_bool("core.bare", false).into_pyresult()?;
        config
            .set_bool("core.logallrefupdates", true)
            .into_pyresult()?;
        config
            .set_str("core.worktree", &self.workspace.to_string_lossy())
            .into_pyresult()?;
        config.set_str("user.name", "Agent").into_pyresult()?;
        config
            .set_str("user.email", "placeholder@example.com")
            .into_pyresult()?;
        Ok(self)
    }


    #[inline]
    fn access_repo(&self) -> PyResult<MutexGuard<'_, Repository>> {
        self.repo.lock().into_pyresult()
    }

    #[inline]
    fn norm_repo_rel_path<P: AsRef<Path>>(&self, file_path: P) -> PyResult<PathBuf> {
        normalized_rel_path(&self.workspace, file_path.as_ref().to_path_buf())
    }
}


#[gen_stub_pymethods]
#[pymethods]
impl CheckPointStore {
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
    #[pyo3(signature=( commit_msg=None))]
    pub fn save(&self, commit_msg: Option<String>) -> PyResult<String> {
        let repo = self.access_repo()?;
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
    pub fn commits(&self) -> PyResult<Vec<String>> {
        let repo = self.access_repo()?;
        let mut revwk = repo.revwalk().into_pyresult()?;
        revwk.push_head().into_pyresult()?;
        Ok(revwk
            .filter_map(Result::ok)
            .map(|oid| oid.to_string())
            .skip(1) // skip the Initial commit which is a placeholder
            .collect())
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
    pub fn reset(&self, commit_id: String) -> PyResult<()> {
        let repo = self.access_repo()?;
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
        commit_id: String,
        file_path: PathBuf,
    ) -> PyResult<()> {
        let norm_file_path = self.norm_repo_rel_path(&file_path)?;
        let repo = self.access_repo()?;
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
            .get_path(&norm_file_path)
            .into_pyresult()?;

        let blob = repo.find_blob(file_obj.id()).into_pyresult()?;
        fs::write(file_path, blob.content()).into_pyresult()
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
        commit_id: String,
        file_path: PathBuf,
    ) -> PyResult<String> {
        let file_path = self.norm_repo_rel_path(file_path)?;
        let repo = self.access_repo()?;
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


    pub fn get_changed_files(
        &self,
        _commit_id: String,
    ) -> PyResult<Vec<String>> {
        todo!()
    }
}
