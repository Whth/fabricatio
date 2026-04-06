use crate::constants::SCHEMA;
use crate::store::MemoryStore;
use crate::utils::{is_valid_index_dir, sanitize_index_name};
use error_mapping::AsPyErr;
use moka::sync::Cache;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tantivy::directory::*;
use tantivy::{Index, IndexWriter};

type IndexName = String;

/// Service class for managing memory stores and indexes.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct MemoryService {
    store_root_directory: PathBuf,
    index_cache: Cache<IndexName, Arc<Index>>,
    index_writer_cache: Cache<IndexName, Arc<Mutex<IndexWriter>>>,
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

        self.index_cache
            .try_get_with(index_name, || {
                Index::open_or_create(MmapDirectory::open(index_path)?, SCHEMA.clone())
                    .map(Arc::new)
            })
            .into_pyresult()
    }

    fn get_index_writer(&self, index_name: IndexName) -> PyResult<Arc<Mutex<IndexWriter>>> {
        self.index_writer_cache
            .try_get_with(index_name.clone(), || {
                let index = self.get_index(index_name)?;
                let index_writer = index.writer(self.writer_buffer_size).into_pyresult()?;
                Ok(Arc::new(Mutex::new(index_writer)))
            })
            .map_err(|e: Arc<PyErr>| Arc::try_unwrap(e).expect("Unable to unwrap Arc"))
    }
}
#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl MemoryService {
    /// Creates a new MemoryService instance.
    ///
    /// Args:
    ///     store_root_directory (pathlib.Path): The root directory where indexes will be stored.
    ///     writer_buffer_size (int, optional): The buffer size for index writers in bytes. Defaults to 15,000,000 (15MB).
    ///     cache_size (int, optional): The maximum number of indexes to keep in cache. Defaults to 10.
    ///
    /// Returns:
    ///     MemoryService: A new instance of the MemoryService.
    #[new]
    #[pyo3(signature = (store_root_directory , writer_buffer_size = 15_000_000,cache_size = 10))]
    pub fn new(store_root_directory: PathBuf, writer_buffer_size: usize, cache_size: u64) -> Self {
        MemoryService {
            store_root_directory,
            index_cache: Cache::new(cache_size),
            index_writer_cache: Cache::new(cache_size),
            writer_buffer_size,
        }
    }

    /// Gets a MemoryStore instance for the given store name.
    ///
    /// This method retrieves or creates an index for the given store name,
    /// then returns a MemoryStore instance that can be used to perform
    /// operations on that index.
    ///
    /// Args:
    ///     store_name (str): The name of the store to get.
    ///
    /// Returns:
    ///     MemoryStore: A MemoryStore instance for the given store name.
    ///
    /// Raises:
    ///     Exception: If the store name is invalid, if there's an error creating or opening the index,
    ///                or if there's an error creating the MemoryStore instance.
    pub fn get_store(&self, store_name: IndexName) -> PyResult<MemoryStore> {
        let index = self.get_index(store_name.clone())?;

        MemoryStore::new(index, self.get_index_writer(store_name)?)
    }

    /// Lists all stores in the system.
    ///
    /// This method returns a list of all store names. It can optionally return
    /// only the stores that are currently cached in memory.
    ///
    /// Args:
    ///     cached_only (bool, optional): If True, only return stores that are currently cached in memory.
    ///                                   If False (default), return all stores in the store directory.
    ///
    /// Returns:
    ///     list[str]: A list of store names.
    ///
    /// Raises:
    ///     Exception: If there's an error reading the store directory.
    #[pyo3(signature = (cached_only = false))]
    pub fn list_stores(&self, cached_only: bool) -> PyResult<Vec<String>> {
        if !self.store_root_directory.exists() {
            return Ok(vec![]);
        }

        if cached_only {
            return Ok(self
                .index_cache
                .iter()
                .map(|(k, _)| k.to_string())
                .collect());
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
