use crate::constants::SCHEMA;
use crate::memory::Memory;
use crate::store::MemoryStore;
use crate::utils::{is_valid_index_dir, sanitize_index_name};
use error_mapping::AsPyErr;
use moka::sync::Cache;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::{PyModule, PyModuleMethods};
use pyo3::{Bound, PyResult, Python, pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tantivy::Index;
use tantivy::directory::*;

type IndexName = String;

#[gen_stub_pyclass]
#[pyclass]
pub struct MemoryService {
    store_root_directory: PathBuf,
    cache: Cache<IndexName, Arc<Index>>,
    writer_buffer_size: usize,
}

impl MemoryService {
    #[inline]
    fn index_path_of<S: AsRef<str>>(&self, index_name: S) -> PyResult<PathBuf> {
        sanitize_index_name(&index_name)?;
        Ok(self
            .store_root_directory
            .join(Path::new(index_name.as_ref())))
    }

    fn get_index(&self, index_name: IndexName) -> PyResult<Arc<Index>> {
        let index_path = self.index_path_of(&index_name)?;
        fs::create_dir_all(&index_path).into_pyresult()?;

        self.cache
            .try_get_with(index_name.clone(), || {
                Index::open_or_create(MmapDirectory::open(index_path)?, SCHEMA.clone())
                    .map(|index| Arc::new(index))
            })
            .into_pyresult()
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl MemoryService {
    /// Create a new MemorySystem with optional index path and writer buffer size
    #[new]
    #[pyo3(signature = (store_root_directory , writer_buffer_size = 50_000_000,cache_size = 10))]
    pub fn new(store_root_directory: PathBuf, writer_buffer_size: usize, cache_size: u64) -> Self {
        let schema = SCHEMA.clone();

        MemoryService {
            store_root_directory,
            cache: Cache::new(cache_size),
            writer_buffer_size,
        }
    }

    pub fn get_store(&self, store_name: IndexName) -> PyResult<MemoryStore> {
        let index = self.get_index(store_name)?;
        Ok(MemoryStore::new(index, self.writer_buffer_size))
    }

    #[pyo3(signature = (cached_only = false))]
    pub fn list_stores(&self, cached_only: bool) -> PyResult<Vec<String>> {
        if !self.store_root_directory.exists() {
            return Ok(vec![]);
        }

        if cached_only {
            return Ok(self.cache.iter().map(|(k, _)| k.to_string()).collect());
        }

        Ok(fs::read_dir(&self.store_root_directory)
            .into_pyresult()?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| is_valid_index_dir(path))
            .map(|path| path.file_name().unwrap().to_string_lossy().to_string())
            .collect())
    }
}
