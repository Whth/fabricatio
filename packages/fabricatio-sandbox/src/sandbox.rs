use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::io::{Read, Write};
use std::path::PathBuf;

use pyo3::prelude::*;
use pyo3::types::PyDict;
use vfs::{MemoryFS, OverlayFS, PhysicalFS, VfsPath};

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

/// Thin wrapper around [`VfsPath`] exposing filesystem operations to Python.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(unsendable)]
pub struct VirtualFS {
    pub(crate) root: VfsPath,
}

fn ensure_parent(p: &VfsPath) {
    let parent = p.parent();
    if parent != *p {
        let _ = parent.create_dir_all();
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl VirtualFS {
    /// Create an empty in-memory virtual filesystem.
    #[staticmethod]
    fn from_memory() -> Self {
        Self {
            root: MemoryFS::new().into(),
        }
    }

    /// Wrap a real directory as a read-only virtual filesystem.
    #[staticmethod]
    fn from_physical(root: &str) -> Self {
        Self {
            root: PhysicalFS::new(PathBuf::from(root)).into(),
        }
    }

    /// Layer an in-memory upper layer over read-only real directories.
    ///
    /// Writes go to the in-memory layer; reads fall through to the real dirs.
    #[staticmethod]
    fn from_overlay(real_roots: Vec<String>) -> Self {
        let upper: VfsPath = MemoryFS::new().into();
        let mut layers = vec![upper];
        for r in &real_roots {
            layers.push(PhysicalFS::new(PathBuf::from(r)).into());
        }
        Self {
            root: OverlayFS::new(&layers).into(),
        }
    }

    /// Read a text file and return its content as a string.
    fn read_text(&self, path: &str) -> PyResult<String> {
        self.root
            .join(path)
            .and_then(|p| p.read_to_string())
            .map_err(vfs_err)
    }

    /// Write text content to a file, creating parent directories as needed.
    fn write_text(&self, path: &str, content: &str) -> PyResult<()> {
        let p = self.root.join(path).map_err(vfs_err)?;
        ensure_parent(&p);
        let mut f = p.create_file().map_err(vfs_err)?;
        f.write_all(content.as_bytes()).map_err(io_err)
    }

    /// Read a file and return its content as bytes.
    fn read_bytes(&self, path: &str) -> PyResult<Vec<u8>> {
        let mut buf = Vec::new();
        self.root
            .join(path)
            .and_then(|p| {
                p.open_file()?
                    .read_to_end(&mut buf)
                    .map_err(vfs::VfsError::from)
            })
            .map_err(vfs_err)?;
        Ok(buf)
    }

    /// Write raw bytes to a file, creating parent directories as needed.
    fn write_bytes(&self, path: &str, content: Vec<u8>) -> PyResult<()> {
        let p = self.root.join(path).map_err(vfs_err)?;
        ensure_parent(&p);
        let mut f = p.create_file().map_err(vfs_err)?;
        f.write_all(&content).map_err(io_err)
    }

    /// List immediate children of a directory, returning filenames.
    fn list_dir(&self, path: &str) -> PyResult<Vec<String>> {
        let p = self.root.join(path).map_err(vfs_err)?;
        let mut names = Vec::new();
        for entry in p.read_dir().map_err(vfs_err)? {
            names.push(entry.filename());
        }
        Ok(names)
    }

    /// Recursively walk a directory, returning all descendant paths.
    fn walk_dir(&self, path: &str) -> PyResult<Vec<String>> {
        let p = self.root.join(path).map_err(vfs_err)?;
        let mut paths = Vec::new();
        for entry in p.walk_dir().map_err(vfs_err)? {
            paths.push(entry.map_err(vfs_err)?.as_str().to_owned());
        }
        Ok(paths)
    }

    /// Check whether a path exists.
    fn exists(&self, path: &str) -> PyResult<bool> {
        self.root
            .join(path)
            .and_then(|p| p.exists())
            .map_err(vfs_err)
    }

    /// Check whether a path is a file.
    fn is_file(&self, path: &str) -> PyResult<bool> {
        self.root
            .join(path)
            .and_then(|p| p.is_file())
            .map_err(vfs_err)
    }

    /// Check whether a path is a directory.
    fn is_dir(&self, path: &str) -> PyResult<bool> {
        self.root
            .join(path)
            .and_then(|p| p.is_dir())
            .map_err(vfs_err)
    }

    /// Create a single directory level at the given path.
    fn create_dir(&self, path: &str) -> PyResult<()> {
        self.root
            .join(path)
            .and_then(|p| p.create_dir())
            .map_err(vfs_err)
    }

    /// Create a directory and all missing ancestors.
    fn create_dir_all(&self, path: &str) -> PyResult<()> {
        self.root
            .join(path)
            .and_then(|p| p.create_dir_all())
            .map_err(vfs_err)
    }

    /// Remove a single file.
    fn remove_file(&self, path: &str) -> PyResult<()> {
        self.root
            .join(path)
            .and_then(|p| p.remove_file())
            .map_err(vfs_err)
    }

    /// Remove a directory and all its contents.
    fn remove_dir_all(&self, path: &str) -> PyResult<()> {
        self.root
            .join(path)
            .and_then(|p| p.remove_dir_all())
            .map_err(vfs_err)
    }

    /// Copy a file from *src* to *dst*, creating parent dirs for *dst*.
    fn copy_file(&self, src: &str, dst: &str) -> PyResult<()> {
        let src_p = self.root.join(src).map_err(vfs_err)?;
        let dst_p = self.root.join(dst).map_err(vfs_err)?;
        ensure_parent(&dst_p);
        src_p.copy_file(&dst_p).map_err(vfs_err)
    }

    /// Move (rename) a file from *src* to *dst*.
    fn rename(&self, src: &str, dst: &str) -> PyResult<()> {
        let src_p = self.root.join(src).map_err(vfs_err)?;
        let dst_p = self.root.join(dst).map_err(vfs_err)?;
        ensure_parent(&dst_p);
        src_p.move_file(&dst_p).map_err(vfs_err)
    }

    /// Return the resolved absolute path string within the VFS.
    fn abs_path(&self, path: &str) -> PyResult<String> {
        self.root
            .join(path)
            .map(|p| p.as_str().to_owned())
            .map_err(vfs_err)
    }

    fn __repr__(&self) -> String {
        format!("VirtualFS(root='{}')", self.root.as_str())
    }
}

// ---------------------------------------------------------------------------
// SandboxSession
// ---------------------------------------------------------------------------

/// High-level sandbox: in-memory upper layer + optional read-only real-dir mounts.
///
/// Tracks original file content on first mutation so `diff()` produces
/// per-file unified diffs and `apply()` can flush changes to the real FS.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(unsendable)]
pub struct SandboxSession {
    vfs: VirtualFS,
    #[allow(dead_code)] // held to keep PhysicalFS instances alive
    overlays: Vec<VfsPath>,
    originals: RefCell<HashMap<String, String>>,
    written: RefCell<HashSet<String>>,
    mounts: HashMap<String, String>,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl SandboxSession {
    /// Create a sandbox session with read-only real-directory mounts.
    ///
    /// ``mounts`` maps virtual paths (e.g. ``"/project"``) to real directories.
    /// All writes go to the in-memory upper layer; reads fall through to the
    /// mounted real directories.
    #[staticmethod]
    fn with_mounts(mounts: HashMap<String, String>) -> PyResult<Self> {
        let upper: VfsPath = MemoryFS::new().into();
        let mut overlays = Vec::with_capacity(mounts.len());
        for real_path in mounts.values() {
            overlays.push(PhysicalFS::new(PathBuf::from(real_path)).into());
        }

        let mut layers = Vec::with_capacity(1 + overlays.len());
        layers.push(upper.clone());
        layers.extend(overlays.iter().cloned());

        let root: VfsPath = OverlayFS::new(&layers).into();

        Ok(Self {
            vfs: VirtualFS { root },
            overlays,
            originals: RefCell::new(HashMap::new()),
            written: RefCell::new(HashSet::new()),
            mounts,
        })
    }

    // -- VFS operations (delegated) -------------------------------------------

    /// Read a text file from the sandbox, resolving mount prefixes.
    fn read_text(&self, path: &str) -> PyResult<String> {
        self.vfs.read_text(&self.resolve_path(path))
    }

    /// Write text to a file, snapshotting the original before first mutation.
    fn write_text(&self, path: &str, content: &str) -> PyResult<()> {
        self.snapshot_if_needed(path);
        self.written.borrow_mut().insert(path.to_owned());
        self.vfs.write_text(&self.resolve_path(path), content)
    }

    /// Read a file and return its content as bytes.
    fn read_bytes(&self, path: &str) -> PyResult<Vec<u8>> {
        self.vfs.read_bytes(&self.resolve_path(path))
    }

    /// Write raw bytes to a file, snapshotting the original before first mutation.
    fn write_bytes(&self, path: &str, content: Vec<u8>) -> PyResult<()> {
        self.snapshot_if_needed(path);
        self.written.borrow_mut().insert(path.to_owned());
        self.vfs.write_bytes(&self.resolve_path(path), content)
    }

    /// List immediate children of a directory.
    fn list_dir(&self, path: &str) -> PyResult<Vec<String>> {
        self.vfs.list_dir(&self.resolve_path(path))
    }

    /// Recursively walk a directory, returning all descendant paths.
    fn walk_dir(&self, path: &str) -> PyResult<Vec<String>> {
        self.vfs.walk_dir(&self.resolve_path(path))
    }

    /// Check whether a path exists in the sandbox.
    fn exists(&self, path: &str) -> PyResult<bool> {
        self.vfs.exists(&self.resolve_path(path))
    }

    /// Check whether a path is a file.
    fn is_file(&self, path: &str) -> PyResult<bool> {
        self.vfs.is_file(&self.resolve_path(path))
    }

    /// Check whether a path is a directory.
    fn is_dir(&self, path: &str) -> PyResult<bool> {
        self.vfs.is_dir(&self.resolve_path(path))
    }

    /// Create a single directory level.
    fn create_dir(&self, path: &str) -> PyResult<()> {
        self.vfs.create_dir(&self.resolve_path(path))
    }

    /// Create a directory and all missing ancestors.
    fn create_dir_all(&self, path: &str) -> PyResult<()> {
        self.vfs.create_dir_all(&self.resolve_path(path))
    }

    /// Remove a single file, snapshotting its content first.
    fn remove_file(&self, path: &str) -> PyResult<()> {
        self.snapshot_if_needed(path);
        self.vfs.remove_file(&self.resolve_path(path))
    }

    /// Remove a directory and all its contents.
    fn remove_dir_all(&self, path: &str) -> PyResult<()> {
        self.vfs.remove_dir_all(&self.resolve_path(path))
    }

    /// Copy a file from *src* to *dst*, snapshotting *dst* first.
    fn copy_file(&self, src: &str, dst: &str) -> PyResult<()> {
        self.snapshot_if_needed(dst);
        self.written.borrow_mut().insert(dst.to_owned());
        self.vfs
            .copy_file(&self.resolve_path(src), &self.resolve_path(dst))
    }

    /// Move a file from *src* to *dst*, snapshotting both first.
    fn rename(&self, src: &str, dst: &str) -> PyResult<()> {
        self.snapshot_if_needed(src);
        self.snapshot_if_needed(dst);
        self.written.borrow_mut().insert(dst.to_owned());
        self.vfs
            .rename(&self.resolve_path(src), &self.resolve_path(dst))
    }

    /// Return the resolved absolute path string within the VFS.
    fn abs_path(&self, path: &str) -> PyResult<String> {
        self.vfs.abs_path(&self.resolve_path(path))
    }

    // -- Session operations ---------------------------------------------------

    /// Return ``{virtual_path: unified_diff, ...}`` for every mutated file.
    fn diff<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let originals = self.originals.borrow();
        let dict = PyDict::new(py);

        for (user_path, original) in originals.iter() {
            let vfs_path = self.resolve_path(user_path);
            if let Ok(current) = self.vfs.read_text(&vfs_path) {
                if &current != original {
                    dict.set_item(user_path, unified_diff(original, &current, user_path))?;
                }
            }
        }

        Ok(dict)
    }

    /// Flush mutations from the in-memory layer back to the real filesystem using the mount mappings.
    ///
    /// Only files that were written through the session are flushed.
    /// New files are created under the matching mount's real directory;
    /// existing files are overwritten.
    fn apply(&self) -> PyResult<()> {
        let written = self.written.borrow();
        for user_path in written.iter() {
            let vfs_path = self.resolve_path(user_path);
            if let Some((_, real_root)) = self
                .mounts
                .iter()
                .find(|(vprefix, _)| self.matches_prefix(user_path, vprefix))
            {
                let rel = self.strip_mount_prefix(user_path);
                let real_path = format!("{}/{}", real_root.trim_end_matches('/'), rel);
                if let Ok(content) = self.vfs.read_bytes(&vfs_path) {
                    let path = std::path::Path::new(&real_path);
                    if let Some(parent) = path.parent() {
                        std::fs::create_dir_all(parent).map_err(io_err)?;
                    }
                    std::fs::write(path, &content).map_err(io_err)?;
                }
            }
        }
        Ok(())
    }

    /// Clear tracked originals and written paths so the next ``diff()`` captures only fresh changes.
    fn reset(&mut self) {
        self.originals.borrow_mut().clear();
        self.written.borrow_mut().clear();
    }

    /// The virtual root path string. Returns ``"/"`` when the overlay root has no explicit path.
    fn root_path(&self) -> String {
        let s = self.vfs.root.as_str();
        if s.is_empty() {
            "/".to_owned()
        } else {
            s.to_owned()
        }
    }

    /// Copy of the current mount mappings.
    fn mounts(&self) -> HashMap<String, String> {
        self.mounts.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "SandboxSession(root='{}', mounts={})",
            self.root_path(),
            self.mounts.len()
        )
    }
}

impl SandboxSession {
    /// Translate a user-facing path (possibly with mount prefix) to an
    /// internal VFS path by stripping the mount prefix and leading `/`.
    fn resolve_path(&self, path: &str) -> String {
        let stripped = path.trim_start_matches('/');
        for mount_prefix in self.mounts.keys() {
            let prefix = mount_prefix.trim_start_matches('/').trim_end_matches('/');
            if stripped == prefix {
                return String::new();
            }
            let prefix_slash = format!("{}/", prefix);
            if stripped.starts_with(&prefix_slash) {
                return stripped[prefix.len() + 1..].to_owned();
            }
        }
        stripped.to_owned()
    }

    /// Check if a user-facing path starts with a mount prefix.
    fn matches_prefix(&self, path: &str, mount_prefix: &str) -> bool {
        let stripped = path.trim_start_matches('/');
        let prefix = mount_prefix.trim_start_matches('/').trim_end_matches('/');
        stripped == prefix || stripped.starts_with(&format!("{}/", prefix))
    }

    /// Strip the mount prefix from a user-facing path, returning the
    /// relative portion suitable for joining with the real root.
    fn strip_mount_prefix<'a>(&self, path: &'a str) -> &'a str {
        let stripped = path.trim_start_matches('/');
        for mount_prefix in self.mounts.keys() {
            let prefix = mount_prefix.trim_start_matches('/').trim_end_matches('/');
            if stripped == prefix {
                return "";
            }
            let prefix_slash = format!("{}/", prefix);
            if stripped.starts_with(&prefix_slash) {
                return &stripped[prefix.len() + 1..];
            }
        }
        stripped
    }

    /// Snapshot the original content of `path` before first mutation.
    fn snapshot_if_needed(&self, user_path: &str) {
        let mut originals = self.originals.borrow_mut();
        if originals.contains_key(user_path) {
            return;
        }
        let vfs_path = self.resolve_path(user_path);
        if let Ok(original) = self.vfs.read_text(&vfs_path) {
            originals.insert(user_path.to_owned(), original);
        }
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn vfs_err(e: vfs::VfsError) -> PyErr {
    pyo3::exceptions::PyRuntimeError::new_err(e.to_string())
}

fn io_err(e: std::io::Error) -> PyErr {
    pyo3::exceptions::PyRuntimeError::new_err(e.to_string())
}

fn unified_diff(old: &str, new: &str, path: &str) -> String {
    use similar::TextDiff;
    let diff = TextDiff::from_lines(old, new);
    let mut out = String::with_capacity(old.len().max(new.len()));
    out.push_str(&format!("--- a/{path}\n+++ b/{path}\n"));
    for hunk in diff.unified_diff().context_radius(3).iter_hunks() {
        out.push_str(&format!("{hunk}\n"));
    }
    out
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VirtualFS>()?;
    m.add_class::<SandboxSession>()?;
    Ok(())
}
