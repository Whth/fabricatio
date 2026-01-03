use crate::constants::SCHEMA;
use crate::store::MemoryStore;
use crate::utils::{is_valid_index_dir, sanitize_index_name};
use error_mapping::AsPyErr;
use moka::sync::Cache;
use pyo3::prelude::*;
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
                    .map(Arc::new)
            })
            .into_pyresult()
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl MemoryService {
    /// Creates a new MemoryService instance
    ///
    /// # Arguments
    /// * `store_root_directory` - The root directory where indexes will be stored
    /// * `writer_buffer_size` - The buffer size for index writers (default: 10MB)
    /// * `cache_size` - The maximum number of indexes to keep in cache (default: 10)
    #[new]
    #[pyo3(signature = (store_root_directory , writer_buffer_size = 10_000_000,cache_size = 10))]
    pub fn new(store_root_directory: PathBuf, writer_buffer_size: usize, cache_size: u64) -> Self {
        MemoryService {
            store_root_directory,
            cache: Cache::new(cache_size),
            writer_buffer_size,
        }
    }

    /// Get a MemoryStore instance for the given store name
    ///
    /// This method retrieves or creates an index for the given store name,
    /// then returns a MemoryStore instance that can be used to perform
    /// operations on that index.
    ///
    /// # Arguments
    /// * `store_name` - The name of the store to get
    ///
    /// # Returns
    /// * `PyResult<MemoryStore>` - A MemoryStore instance for the given store name
    ///
    /// # Errors
    /// * If the store name is invalid
    /// * If there's an error creating or opening the index
    /// * If there's an error creating the MemoryStore instance
    pub fn get_store(&self, store_name: IndexName) -> PyResult<MemoryStore> {
        let index = self.get_index(store_name)?;
        MemoryStore::new(index, self.writer_buffer_size)
    }

    /// List all stores in the system
    ///
    /// This method returns a list of all store names. It can optionally return
    /// only the stores that are currently cached in memory.
    ///
    /// # Arguments
    /// * `cached_only` - If true, only return stores that are currently cached in memory.
    ///                   If false (default), return all stores in the store directory.
    ///
    /// # Returns
    /// * `PyResult<Vec<String>>` - A vector of store names
    ///
    /// # Errors
    /// * If there's an error reading the store directory
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
            .filter(is_valid_index_dir)
            .map(|path| path.file_name().unwrap().to_string_lossy().to_string())
            .collect())
    }
}
