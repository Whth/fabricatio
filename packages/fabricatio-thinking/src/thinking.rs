use fabricatio_logger::*;
use fabricatio_logger::*;
use pyo3::prelude::*;
use std::collections::HashMap;
/// Represents a branch in the version control system, containing a list of commits and an estimated total number of commits.
#[derive(Default, Debug)]
struct Branch {
    /// Estimated total number of commits expected in this branch.
    estimated: usize,
    /// List of commits in this branch.
    commits: Vec<String>,
}

impl Branch {
    /// Adds a new commit to the branch if the serial matches the next expected commit index.
    ///
    /// # Arguments
    ///
    /// * `content` - The content of the commit.
    /// * `serial` - The serial number (1-based) of the commit to be added.
    ///
    /// # Returns
    ///
    /// Returns `Some(new_commit_count)` if the commit was added, or `None` if the serial does not match.
    fn commit(&mut self, content: String, serial: usize) -> Option<usize> {
        if serial - 1 != self.commits.len() {
            warn!(
                "Serial mismatch: expected {}, got {}, discard this commit: {content}",
                serial,
                self.commits.len()
            );
            None
        } else {
            self.commits.push(content);
            Some(self.commits.len())
        }
    }

    /// Sets the estimated total number of commits for this branch.
    ///
    /// # Arguments
    ///
    /// * `estimated` - The new estimated number of commits.
    ///
    /// # Returns
    ///
    /// Returns a mutable reference to self for chaining.
    fn estimate(&mut self, estimated: usize) -> &mut Self {
        self.estimated = estimated;
        self
    }
    /// Returns a new `Branch` instance containing commits up to the given serial number.
    ///
    /// # Arguments
    ///
    /// * `serial` - The number of commits to include in the new branch (exclusive).
    ///
    /// # Returns
    ///
    /// A new `Branch` with commits up to the specified serial.
    fn checkout(&self, serial: usize) -> Option<Self> {
        if serial > self.commits.len() {
            None
        } else {
            Some(Branch {
                commits: self.commits[..serial].to_vec(),
                estimated: self.estimated,
            })
        }
    }

    /// Revises the content of an existing commit at the given serial number.
    ///
    /// # Arguments
    ///
    /// * `content` - The new content for the commit.
    /// * `serial` - The serial number (1-based) of the commit to revise.
    ///
    /// # Returns
    ///
    /// Returns `Some(serial)` if the commit was revised, or `None` if the serial is out of bounds.
    fn revise(&mut self, content: String, serial: usize) -> Option<usize> {
        if serial > self.commits.len() {
            None
        } else {
            self.commits[serial - 1] = content;
            Some(serial)
        }
    }
}

/// Represents a simple version control system for managing branches and their commits.
#[pyclass]
#[derive(Default, Debug)]
struct ThoughtVCS {
    /// Map of branch names to their corresponding `Branch` instances.
    branches: HashMap<Option<String>, Branch>,
}

impl ThoughtVCS {
    /// Retrieves a mutable reference to a branch by name, optionally inserting it if it does not exist.
    ///
    /// # Arguments
    ///
    /// * `name` - The name of the branch, or `None` for the default branch.
    /// * `insert` - Whether to insert the branch if it does not exist.
    ///
    /// # Returns
    ///
    /// Returns a mutable reference to the branch if found or inserted, otherwise `None`.
    fn branch(&mut self, name: Option<String>, insert: bool) -> Option<&mut Branch> {
        if !self.branches.contains_key(&name) && insert {
            self.branches.insert(name.clone(), Branch::default());
        }
        self.branches.get_mut(&name)
    }
}

#[pymethods]
impl ThoughtVCS {
    /// Creates a new instance of `ThoughtVCS` with default branches.
    ///
    /// # Returns
    ///
    /// A new `ThoughtVCS` instance initialized with default branch data.
    #[new]
    fn new() -> Self {
        ThoughtVCS::default()
    }
    /// Commits new content to a branch, creating the branch if necessary.
    ///
    /// # Arguments
    ///
    /// * `content` - The content of the commit.
    /// * `serial` - The serial number (1-based) for the commit.
    /// * `estimated` - The estimated total number of commits for the branch.
    /// * `branch` - The name of the branch, or `None` for the default branch.
    /// * `insert` - Whether to create the branch if it does not exist.
    ///
    /// # Returns
    ///
    /// Returns `Some(new_commit_count)` if the commit was added, or `None` otherwise.
    #[pyo3(signature=(content,serial,estimated,branch=None,insert=true))]
    fn commit(
        &mut self,
        content: String,
        serial: usize,
        estimated: usize,
        branch: Option<String>,
        insert: bool,
    ) -> Option<usize> {
        self.branch(branch, insert)
            .and_then(|branch| branch.estimate(estimated).commit(content, serial))
    }

    /// Revises the content of an existing commit in a branch.
    ///
    /// # Arguments
    ///
    /// * `content` - The new content for the commit.
    /// * `serial` - The serial number (1-based) of the commit to revise.
    /// * `branch` - The name of the branch, or `None` for the default branch.
    ///
    /// # Returns
    ///
    /// Returns `Some(serial)` if the commit was revised, or `None` otherwise.
    fn revise(&mut self, content: String, serial: usize, branch: Option<String>) -> Option<usize> {
        self.branch(branch, false)
            .and_then(|branch| branch.revise(content, serial))
    }

    /// Checks out a branch at a specific commit serial, truncating it to that point.
    ///
    /// # Arguments
    ///
    /// * `branch` - The name of the branch to checkout.
    /// * `serial` - The number of commits to include in the checked-out branch.
    ///
    /// # Returns
    ///
    /// Returns `Some(branch_name)` if the checkout was successful, or `None` otherwise.
    fn checkout(&mut self, branch: String, serial: usize) -> Option<String> {
        if let Some(br) = self
            .branch(Some(branch.clone()), false)
            .and_then(|branch| branch.checkout(serial))
        {
            self.branches.insert(Some(branch.clone()), br);
            Some(branch)
        } else {
            None
        }
    }

    /// Exports the list of commits for a given branch.
    ///
    /// This function retrieves all commits associated with the specified branch.
    /// If the branch does not exist, it returns an empty vector.
    ///
    /// # Arguments
    ///
    /// * `branch` - An optional string representing the name of the branch.
    ///              If `None`, the default branch is used.
    ///
    /// # Returns
    ///
    /// A vector of strings where each string represents a commit in the branch.
    /// If the branch does not exist and cannot be found, an empty vector is returned.
    #[pyo3(signature = (branch = None))]
    fn export_branch(&mut self, branch: Option<String>) -> Vec<String> {
        self.branch(branch, false)
            .map(|branch| branch.commits.clone())
            .unwrap_or_default()
    }

    ///
    /// # Arguments
    ///
    /// * `branch` - An optional string representing the name of the branch.
    ///              If `None`, the default branch is used.
    ///
    /// # Returns
    ///
    /// A formatted string where each line represents a commit in the branch, prefixed with "- ".
    /// If the branch does not exist, returns an empty string.
    #[pyo3(signature = (branch = None))]
    fn export_branch_string(&mut self, branch: Option<String>) -> String {
        self.branch(branch, false)
            .map(|branch| {
                branch
                    .commits
                    .iter()
                    .enumerate()
                    .map(|(i, commit)| format!("Serial {}: {commit}\n", i + 1))
                    .collect::<String>()
            })
            .unwrap_or_default()
    }
}

/// Registers the `ThoughtVCS` class with the given Python module.
///
/// # Arguments
///
/// * `_` - The Python interpreter instance.
/// * `m` - The Python module to register the class with.
///
/// # Returns
///
/// Returns `PyResult<()>` indicating success or failure.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ThoughtVCS>()?;
    Ok(())
}
