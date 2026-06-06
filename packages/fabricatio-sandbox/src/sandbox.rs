use std::cell::RefCell;
use std::collections::HashMap;
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
    fn read_text(&self, path: &str) -> PyResult<String> {
        self.root
            .join(path)
            .and_then(|p| p.read_to_string())
            .map_err(vfs_err)
    }

    fn write_text(&self, path: &str, content: &str) -> PyResult<()> {
        let p = self.root.join(path).map_err(vfs_err)?;
        ensure_parent(&p);
        let mut f = p.create_file().map_err(vfs_err)?;
        f.write_all(content.as_bytes()).map_err(io_err)
    }

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

    fn write_bytes(&self, path: &str, content: &[u8]) -> PyResult<()> {
        let p = self.root.join(path).map_err(vfs_err)?;
        ensure_parent(&p);
        let mut f = p.create_file().map_err(vfs_err)?;
        f.write_all(content).map_err(io_err)
    }

    fn list_dir(&self, path: &str) -> PyResult<Vec<String>> {
        let p = self.root.join(path).map_err(vfs_err)?;
        let mut names = Vec::new();
        for entry in p.read_dir().map_err(vfs_err)? {
            names.push(entry.filename());
        }
        Ok(names)
    }

    fn walk_dir(&self, path: &str) -> PyResult<Vec<String>> {
        let p = self.root.join(path).map_err(vfs_err)?;
        let mut paths = Vec::new();
        for entry in p.walk_dir().map_err(vfs_err)? {
            paths.push(entry.map_err(vfs_err)?.as_str().to_owned());
        }
        Ok(paths)
    }

    fn exists(&self, path: &str) -> PyResult<bool> {
        self.root.join(path).and_then(|p| p.exists()).map_err(vfs_err)
    }

    fn is_file(&self, path: &str) -> PyResult<bool> {
        self.root.join(path).and_then(|p| p.is_file()).map_err(vfs_err)
    }

    fn is_dir(&self, path: &str) -> PyResult<bool> {
        self.root.join(path).and_then(|p| p.is_dir()).map_err(vfs_err)
    }

    fn create_dir(&self, path: &str) -> PyResult<()> {
        self.root.join(path).and_then(|p| p.create_dir()).map_err(vfs_err)
    }

    fn create_dir_all(&self, path: &str) -> PyResult<()> {
        self.root.join(path).and_then(|p| p.create_dir_all()).map_err(vfs_err)
    }

    fn remove_file(&self, path: &str) -> PyResult<()> {
        self.root.join(path).and_then(|p| p.remove_file()).map_err(vfs_err)
    }

    fn remove_dir_all(&self, path: &str) -> PyResult<()> {
        self.root.join(path).and_then(|p| p.remove_dir_all()).map_err(vfs_err)
    }

    fn copy_file(&self, src: &str, dst: &str) -> PyResult<()> {
        let src_p = self.root.join(src).map_err(vfs_err)?;
        let dst_p = self.root.join(dst).map_err(vfs_err)?;
        ensure_parent(&dst_p);
        src_p.copy_file(&dst_p).map_err(vfs_err)
    }

    fn rename(&self, src: &str, dst: &str) -> PyResult<()> {
        let src_p = self.root.join(src).map_err(vfs_err)?;
        let dst_p = self.root.join(dst).map_err(vfs_err)?;
        ensure_parent(&dst_p);
        src_p.move_file(&dst_p).map_err(vfs_err)
    }

    fn abs_path(&self, path: &str) -> PyResult<String> {
        self.root.join(path).map(|p| p.as_str().to_owned()).map_err(vfs_err)
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
    mounts: HashMap<String, String>,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl SandboxSession {
    /// Create a new sandbox session.
    ///
    /// ``mounts`` maps virtual paths to real directories that are mounted
    /// read-only into the overlay; all writes go to the in-memory layer.
    #[new]
    #[pyo3(signature = (mounts=None))]
    fn new(mounts: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let mounts_map: HashMap<String, String> = match mounts {
            Some(d) => d.extract().map_err(|e: PyErr| e)?,
            None => HashMap::new(),
        };

        let upper: VfsPath = MemoryFS::new().into();
        let mut overlays = Vec::with_capacity(mounts_map.len());
        for real_path in mounts_map.values() {
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
            mounts: mounts_map,
        })
    }

    // -- VFS operations (delegated) -------------------------------------------

    fn read_text(&self, path: &str) -> PyResult<String> {
        self.vfs.read_text(path)
    }

    fn write_text(&self, path: &str, content: &str) -> PyResult<()> {
        self.snapshot_if_needed(path);
        self.vfs.write_text(path, content)
    }

    fn read_bytes(&self, path: &str) -> PyResult<Vec<u8>> {
        self.vfs.read_bytes(path)
    }

    fn write_bytes(&self, path: &str, content: &[u8]) -> PyResult<()> {
        self.snapshot_if_needed(path);
        self.vfs.write_bytes(path, content)
    }

    fn list_dir(&self, path: &str) -> PyResult<Vec<String>> {
        self.vfs.list_dir(path)
    }

    fn walk_dir(&self, path: &str) -> PyResult<Vec<String>> {
        self.vfs.walk_dir(path)
    }

    fn exists(&self, path: &str) -> PyResult<bool> {
        self.vfs.exists(path)
    }

    fn is_file(&self, path: &str) -> PyResult<bool> {
        self.vfs.is_file(path)
    }

    fn is_dir(&self, path: &str) -> PyResult<bool> {
        self.vfs.is_dir(path)
    }

    fn create_dir(&self, path: &str) -> PyResult<()> {
        self.vfs.create_dir(path)
    }

    fn create_dir_all(&self, path: &str) -> PyResult<()> {
        self.vfs.create_dir_all(path)
    }

    fn remove_file(&self, path: &str) -> PyResult<()> {
        self.snapshot_if_needed(path);
        self.vfs.remove_file(path)
    }

    fn remove_dir_all(&self, path: &str) -> PyResult<()> {
        self.vfs.remove_dir_all(path)
    }

    fn copy_file(&self, src: &str, dst: &str) -> PyResult<()> {
        self.snapshot_if_needed(dst);
        self.vfs.copy_file(src, dst)
    }

    fn rename(&self, src: &str, dst: &str) -> PyResult<()> {
        self.snapshot_if_needed(src);
        self.snapshot_if_needed(dst);
        self.vfs.rename(src, dst)
    }

    fn abs_path(&self, path: &str) -> PyResult<String> {
        self.vfs.abs_path(path)
    }

    // -- Session operations ---------------------------------------------------

    /// Return ``{virtual_path: unified_diff, ...}`` for every mutated file.
    fn diff<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let all_files = self.collect_vfs_files()?;
        let originals = self.originals.borrow();
        let dict = PyDict::new(py);

        for vp in &all_files {
            if let Some(original) = originals.get(vp.as_str()) {
                if let Ok(current) = self.vfs.read_text(vp) {
                    if &current != original {
                        dict.set_item(vp, unified_diff(original, &current, vp))?;
                    }
                }
            }
        }

        Ok(dict)
    }

    /// Flush mutations from the in-memory layer back to the real filesystem
    /// using the mount mappings.
    fn apply(&self) -> PyResult<()> {
        let all_files = self.collect_vfs_files()?;

        for vp in &all_files {
            if let Some((_, real_root)) = self
                .mounts
                .iter()
                .find(|(vprefix, _)| vp.starts_with(vprefix.trim_start_matches('/')))
            {
                let vprefix = self
                    .mounts
                    .iter()
                    .find(|(_, rr)| **rr == *real_root)
                    .map(|(vp, _)| vp.as_str())
                    .unwrap_or("");

                let rel = vp
                    .strip_prefix(vprefix.trim_start_matches('/'))
                    .unwrap_or(vp)
                    .trim_start_matches('/');
                let real_path = format!("{}/{}", real_root.trim_end_matches('/'), rel);

                if let Ok(content) = self.vfs.read_bytes(vp) {
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

    /// Clear tracked originals so the next `diff()` captures only fresh changes.
    fn reset(&mut self) {
        self.originals.borrow_mut().clear();
    }

    /// The virtual root path string.
    fn root_path(&self) -> &str {
        self.vfs.root.as_str()
    }

    /// Copy of the current mount mappings.
    fn mounts(&self) -> HashMap<String, String> {
        self.mounts.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "SandboxSession(root='{}', mounts={})",
            self.vfs.root.as_str(),
            self.mounts.len()
        )
    }
}

impl SandboxSession {
    /// Snapshot the original content of `path` before first mutation.
    fn snapshot_if_needed(&self, path: &str) {
        let mut originals = self.originals.borrow_mut();
        if originals.contains_key(path) {
            return;
        }
        if let Ok(original) = self.vfs.read_text(path) {
            originals.insert(path.to_owned(), original);
        }
    }

    /// Collect every file path in the merged VFS, skipping `.whiteout` dirs.
    fn collect_vfs_files(&self) -> PyResult<Vec<String>> {
        let root = &self.vfs.root;
        if !root.exists().map_err(vfs_err)? {
            return Ok(Vec::new());
        }
        let mut files = Vec::new();
        for entry in root.walk_dir().map_err(vfs_err)? {
            let e = entry.map_err(vfs_err)?;
            if e.as_str().contains(".whiteout") {
                continue;
            }
            if e.is_file().unwrap_or(false) {
                files.push(e.as_str().to_owned());
            }
        }
        Ok(files)
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
