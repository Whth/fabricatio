use crate::Result;
use crate::utils::{TimeStamp, current_timestamp};
use heed::{Database, Env, EnvOpenOptions, types::*};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use std::fmt::Debug;

use std::path::Path;

/// Default LMDB map size: 1 GiB.
///
/// On Linux this is virtual address space reservation (free). On Windows this
/// pre-allocates disk space, so pick a value that won't waste too much space.
const DEFAULT_MAP_SIZE: usize = 1 << 30; // 1 GiB

/// Named database inside the LMDB environment.
const DB_NAME: &str = "cache";

/// Internal storage format for cache entries.
///
/// Each entry stores the serialized data along with metadata for cache management:
/// - `timestamp`: When the entry was last written (used for TTL tracking)
/// - `access_count`: Number of times the entry has been accessed (for eviction metrics)
/// - `data`: The serialized value as bytes
#[derive(Debug, Default, Deserialize, Serialize)]
struct CacheValue {
    /// Timestamp of the last write operation (milliseconds since epoch).
    timestamp: TimeStamp,
    /// Number of times this entry has been accessed from cache.
    access_count: u64,
    /// Serialized data stored as bytes (via postcard).
    data: Vec<u8>,
}

impl CacheValue {
    /// Deserializes the stored data back into a Rust value.
    fn access_data<T: DeserializeOwned>(&self) -> Result<T> {
        let v = postcard::from_bytes(&self.data)?;
        Ok(v)
    }

    /// Serializes a value and wraps it in a `CacheValue` with a fresh timestamp.
    fn from_data<T: Serialize>(data: T) -> Result<Self> {
        postcard::to_stdvec(&data)
            .map(|e| Self {
                timestamp: current_timestamp(),
                data: e,
                ..CacheValue::default()
            })
            .map_err(|e| e.into())
    }
}

/// A persistent key-value cache backed by [heed](https://github.com/meilisearch/heed) (LMDB).
///
/// `PersistentCache` provides a thread-safe, persistent cache using the LMDB embedded
/// database via the heed crate. It supports serialization/deserialization of any type
/// that implements serde's `Serialize` and `DeserializeOwned` traits.
///
/// # Features
/// - **Persistent storage**: Data survives process restarts
/// - **Multi-process safe**: Multiple processes can access the same database
/// - **Zero-copy reads**: LMDB memory-maps the database for fast reads (OS page cache)
/// - **Serialization support**: Automatic serialization via `get_de` and `set_ser`
///
/// # Example
/// ```no_run
/// use thryd::PersistentCache;
///
/// // Open or create a cache at the given path
/// let cache = PersistentCache::create_or_open("./cache.db").unwrap();
///
/// // Store a serialized value
/// cache.set_ser("key", &"value").unwrap();
///
/// // Retrieve and deserialize
/// if let Some(value) = cache.get_de::<String>("key") {
/// }
/// ```
///
/// # Thread Safety
/// The cache uses `Clone`-able heed types internally, making it safe to clone and share
/// across multiple threads.
#[derive(Clone)]
pub struct PersistentCache {
    /// The LMDB environment (holds the memory map and manages transactions).
    env: Env,
    /// The typed database handle (key: `&str`, value: raw bytes).
    db: Database<Str, Bytes>,
}

impl PersistentCache {
    /// Opens an existing cache database or creates a new one at the specified path.
    ///
    /// Uses the default map size of 1 GiB. For a custom map size, use
    /// [`create_or_open_with_map_size`](Self::create_or_open_with_map_size).
    ///
    /// # Arguments
    /// * `path` - Path to the cache database directory (created if non-existent)
    ///
    /// # Returns
    /// * `Result<Self>` - A new `PersistentCache` instance, or an error if creation/open fails
    pub fn create_or_open(path: impl AsRef<Path>) -> Result<Self> {
        Self::create_or_open_with_map_size(path, DEFAULT_MAP_SIZE)
    }

    /// Opens an existing cache database or creates a new one with a custom map size.
    ///
    /// On Linux, the map size is a virtual address space reservation (free).
    /// On Windows, this pre-allocates disk space, so choose wisely.
    ///
    /// # Arguments
    /// * `path` - Path to the cache database directory (created if non-existent)
    /// * `map_size` - Maximum database size in bytes
    ///
    /// # Returns
    /// * `Result<Self>` - A new `PersistentCache` instance, or an error if creation/open fails
    pub fn create_or_open_with_map_size(path: impl AsRef<Path>, map_size: usize) -> Result<Self> {
        let path = path.as_ref();

        // LMDB requires the path to be a directory. If a file exists at this path
        // (e.g. from a previous redb database), remove it so we can create the dir.
        if path.is_file() {
            std::fs::remove_file(path).map_err(heed::Error::Io)?;
        }
        std::fs::create_dir_all(path).map_err(heed::Error::Io)?;

        let mut env_builder = EnvOpenOptions::new();
        env_builder.map_size(map_size);
        env_builder.max_dbs(1);

        // SAFETY: We ensure the path exists and we only open each environment once
        // per process (the caller is responsible for not opening the same path twice).
        let env = unsafe { env_builder.open(path)? };

        let mut wtxn = env.write_txn()?;
        let db = env.create_database(&mut wtxn, Some(DB_NAME))?;
        wtxn.commit()?;

        Ok(Self { env, db })
    }

    /// Retrieves and deserializes a value from the cache.
    ///
    /// # Type Parameters
    /// * `T` - The type to deserialize to (must implement `DeserializeOwned` and `Clone`)
    ///
    /// # Arguments
    /// * `key` - The cache key to look up
    ///
    /// # Returns
    /// * `Option<T>` - The deserialized value if the key exists, `None` otherwise
    ///
    /// # Example
    /// ```no_run
    /// use thryd::PersistentCache;
    ///
    /// let cache = PersistentCache::create_or_open("./cache.db").unwrap();
    ///
    /// if let Some(value) = cache.get_de::<String>("my-key") {
    ///     println!("Cached value: {}", value);
    /// }
    /// ```
    pub fn get_de<T: DeserializeOwned + Clone>(&self, key: &str) -> Option<T> {
        let rtxn = self.env.read_txn().ok()?;
        let bytes = self.db.get(&rtxn, key).ok()??;
        let cv: CacheValue = postcard::from_bytes(bytes).ok()?;
        cv.access_data::<T>().ok()
    }

    /// Serializes and stores a value in the cache.
    ///
    /// # Type Parameters
    /// * `T` - The type to serialize (must implement `Serialize`)
    ///
    /// # Arguments
    /// * `key` - The cache key
    /// * `value` - A reference to the value to serialize and store
    ///
    /// # Returns
    /// * `Result<()>` - Success, or an error if serialization or storage fails
    ///
    /// # Example
    /// ```no_run
    /// use thryd::PersistentCache;
    ///
    /// let cache = PersistentCache::create_or_open("./cache.db").unwrap();
    /// cache.set_ser("my-key", &"my-value").unwrap();
    /// ```
    pub fn set_ser<T: Serialize>(&self, key: impl AsRef<str>, value: &T) -> Result<()> {
        let cv = CacheValue::from_data(value)?;
        let bytes = postcard::to_stdvec(&cv)?;
        let mut wtxn = self.env.write_txn()?;
        self.db.put(&mut wtxn, key.as_ref(), &bytes)?;
        wtxn.commit()?;
        Ok(())
    }

    /// Checks whether a key exists in the cache.
    ///
    /// # Arguments
    /// * `key` - The cache key to check
    ///
    /// # Returns
    /// * `bool` - `true` if the key exists, `false` otherwise
    pub fn contains_key(&self, key: &str) -> bool {
        let rtxn = match self.env.read_txn() {
            Ok(txn) => txn,
            Err(_) => return false,
        };

        matches!(self.db.get(&rtxn, key), Ok(Some(_)))
    }

    /// Removes a key from the cache.
    ///
    /// # Arguments
    /// * `key` - The cache key to remove
    ///
    /// # Returns
    /// * `Result<()>` - Success, or an error if removal fails
    pub fn remove(&self, key: impl AsRef<str>) -> Result<()> {
        let mut wtxn = self.env.write_txn()?;
        self.db.delete(&mut wtxn, key.as_ref())?;
        wtxn.commit()?;
        Ok(())
    }

    /// Returns the number of entries in the cache.
    ///
    /// # Returns
    /// * `Result<u64>` - The count of entries, or an error if the operation fails
    pub fn len(&self) -> Result<u64> {
        let rtxn = self.env.read_txn()?;
        Ok(self.db.len(&rtxn)?)
    }

    /// Checks whether the cache is empty.
    ///
    /// # Returns
    /// * `Result<bool>` - `true` if empty, `false` otherwise, or an error if check fails
    pub fn is_empty(&self) -> Result<bool> {
        let rtxn = self.env.read_txn()?;
        Ok(self.db.is_empty(&rtxn)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cache_hit() {
        let dir = tempfile::tempdir().unwrap();
        let cache = PersistentCache::create_or_open(dir.path().join("hit.db")).unwrap();
        cache.set_ser("key", &"value".to_string()).unwrap();
        let val: Option<String> = cache.get_de("key");
        assert_eq!(val, Some("value".to_string()));
    }

    #[test]
    fn cache_miss_returns_none() {
        let dir = tempfile::tempdir().unwrap();
        let cache = PersistentCache::create_or_open(dir.path().join("miss.db")).unwrap();
        let val: Option<String> = cache.get_de("nonexistent");
        assert!(val.is_none());
    }

    #[test]
    fn cache_persists_across_instances() {
        let dir = tempfile::tempdir().unwrap();
        let db_path = dir.path().join("persist.db");

        // Write via first instance
        {
            let cache = PersistentCache::create_or_open(&db_path).unwrap();
            cache.set_ser("key", &42u32).unwrap();
        }

        // Read via new instance (simulates restart)
        let cache2 = PersistentCache::create_or_open(&db_path).unwrap();
        let val: Option<u32> = cache2.get_de("key");
        assert_eq!(val, Some(42));
    }

    #[test]
    fn cache_overwrite() {
        let dir = tempfile::tempdir().unwrap();
        let cache = PersistentCache::create_or_open(dir.path().join("overwrite.db")).unwrap();
        cache.set_ser("key", &"old".to_string()).unwrap();
        cache.set_ser("key", &"new".to_string()).unwrap();
        let val: Option<String> = cache.get_de("key");
        assert_eq!(val, Some("new".to_string()));
    }

    #[test]
    fn cache_contains_key() {
        let dir = tempfile::tempdir().unwrap();
        let cache = PersistentCache::create_or_open(dir.path().join("contains.db")).unwrap();
        assert!(!cache.contains_key("k"));
        cache.set_ser("k", &42u32).unwrap();
        assert!(cache.contains_key("k"));
    }

    #[test]
    fn cache_remove() {
        let dir = tempfile::tempdir().unwrap();
        let cache = PersistentCache::create_or_open(dir.path().join("remove.db")).unwrap();
        cache.set_ser("k", &42u32).unwrap();
        assert!(cache.contains_key("k"));
        cache.remove("k").unwrap();
        assert!(!cache.contains_key("k"));
    }

    #[test]
    fn cache_len_and_empty() {
        let dir = tempfile::tempdir().unwrap();
        let cache = PersistentCache::create_or_open(dir.path().join("len.db")).unwrap();
        assert!(cache.is_empty().unwrap());
        assert_eq!(cache.len().unwrap(), 0);

        cache.set_ser("a", &1u32).unwrap();
        cache.set_ser("b", &2u32).unwrap();
        assert_eq!(cache.len().unwrap(), 2);
        assert!(!cache.is_empty().unwrap());
    }
}
