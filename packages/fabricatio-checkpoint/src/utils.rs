use blake3::hash;
use error_mapping::AsPyErr;
use pyo3::PyResult;
use std::path::{absolute, Path, PathBuf};

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