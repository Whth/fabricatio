use crate::Result;
use crate::utils::{TimeStamp, current_timestamp};
use redb::{Database, ReadableDatabase, ReadableTableMetadata, TableDefinition, TypeName, Value};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use std::fmt::Debug;

use std::path::Path;
use std::sync::Arc;

/// Internal storage format for cache entries.
///
/// Each entry stores the serialized data along with metadata for cache management:
/// - `timestamp`: When the entry was last written (used for TTL tracking)
/// - `access_count`: Number of times the entry has been accessed (for eviction metrics)
/// - `data`: The serialized value as bytes
///
/// This struct implements redb's `Value` trait for persistent storage.
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
    ///
    /// # Type Parameter
    /// * `T` - Must implement `DeserializeOwned` and `Clone`
    ///
    /// # Returns
    /// * `Result<T>` - The deserialized value, or an error if deserialization fails
    fn access_data<T: DeserializeOwned>(&self) -> Result<T> {
        let v = postcard::from_bytes(&self.data)?;
        Ok(v)
    }

    /// Serializes a value and wraps it in a `CacheValue` with a fresh timestamp.
    ///
    /// # Type Parameter
    /// * `T` - Must implement `Serialize`
    ///
    /// # Returns
    /// * `Result<CacheValue>` - The serialized cache entry, or an error if serialization fails
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

/// Table definition for the cache storage (redb table name: "cache").
const CACHE_TABLE: TableDefinition<&str, CacheValue> = TableDefinition::new("cache");

/// Implements redb's `Value` trait to enable persistent storage of `CacheValue`.
///
/// This enables redb to serialize/deserialize `CacheValue` entries when storing
/// them in the embedded database. Serialization uses the `postcard` crate.
impl Value for CacheValue {
    type SelfType<'a> = CacheValue;
    type AsBytes<'a> = Vec<u8>;

    fn fixed_width() -> Option<usize> {
        None
    }

    /// Deserialize from bytes using postcard.
    fn from_bytes<'a>(data: &'a [u8]) -> Self::SelfType<'a>
    where
        Self: 'a,
    {
        postcard::from_bytes::<CacheValue>(data).expect("Failed to deserialize cache value")
    }

    /// Serialize to bytes using postcard.
    fn as_bytes<'a, 'b: 'a>(value: &'a Self::SelfType<'b>) -> Self::AsBytes<'a>
    where
        Self: 'b,
    {
        postcard::to_stdvec(value).expect("Fail to serialize cache value")
    }

    fn type_name() -> TypeName {
        TypeName::new("CacheValue")
    }
}

/// A persistent key-value cache backed by [redb](https://github.com/cberner/redb).
///
/// `PersistentCache` provides a thread-safe, persistent cache using the redb embedded
/// database. It supports serialization/deserialization of any type that implements
/// serde's `Serialize` and `DeserializeOwned` traits.
///
/// # Features
/// - **Persistent storage**: Data survives process restarts
/// - **Zero-copy reads**: Internal get operations avoid unnecessary cloning
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
/// if let Some(value) = cache.get_de::<String, _>("key") {
///     println!("Got: {}", value);
/// }
/// ```
///
/// # Thread Safety
/// The cache uses `Arc<Database>` internally, making it safe to clone and share
/// across multiple threads.
#[derive(Clone)]
pub struct PersistentCache {
    /// The underlying redb database instance.
    db: Arc<Database>,
}

impl PersistentCache {
    /// Opens an existing cache database or creates a new one at the specified path.
    ///
    /// If the path already exists, opens the existing database. If the path does not
    /// exist, creates a new database at that location.
    ///
    /// # Arguments
    /// * `path` - Path to the cache database file (created if non-existent)
    ///
    /// # Returns
    /// * `Result<Self>` - A new `PersistentCache` instance, or an error if creation/open fails
    ///
    /// # Example
    /// ```no_run
    /// use thryd::PersistentCache;
    ///
    /// let cache = PersistentCache::create_or_open("./my-cache.db").unwrap();
    /// ```
    pub fn create_or_open(path: impl AsRef<Path>) -> Result<Self> {
        if path.as_ref().exists() {
            Database::open(path.as_ref())
                .map(|db| Self { db: Arc::new(db) })
                .map_err(|e| e.into())
        } else {
            Database::create(path.as_ref())
                .map(|db| Self { db: Arc::new(db) })
                .map_err(|e| e.into())
        }
    }

    /// Retrieves a raw `CacheValue` from the cache by key.
    ///
    /// This is an internal method used by `get_de`. Prefer using `get_de` for
    /// automatic deserialization.
    ///
    /// # Arguments
    /// * `key` - The cache key to look up
    ///
    /// # Returns
    /// * `Option<CacheValue>` - The raw cache entry if found, `None` otherwise
    fn get(&self, key: &str) -> Option<CacheValue> {
        self.db
            .begin_read()
            .ok()?
            .open_table(CACHE_TABLE)
            .ok()?
            .get(key)
            .ok()?
            .map(|e| e.value())
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
    /// if let Some(value) = cache.get_de::<String, _>("my-key") {
    ///     println!("Cached value: {}", value);
    /// }
    /// ```
    pub fn get_de<T: DeserializeOwned + Clone>(&self, key: &str) -> Option<T> {
        self.get(key)?.access_data::<T>().ok()
    }

    /// Stores a raw `CacheValue` in the cache.
    ///
    /// This is an internal method used by `set_ser`. Prefer using `set_ser` for
    /// automatic serialization.
    ///
    /// # Arguments
    /// * `key` - The cache key
    /// * `value` - The `CacheValue` to store
    fn set(&self, key: impl AsRef<str>, value: CacheValue) -> Result<()> {
        let trx = self.db.begin_write()?;

        trx.open_table(CACHE_TABLE)?.insert(key.as_ref(), value)?;

        trx.commit()?;

        Ok(())
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
        self.set(key, CacheValue::from_data(value)?)
    }

    /// Checks whether a key exists in the cache.
    ///
    /// # Arguments
    /// * `key` - The cache key to check
    ///
    /// # Returns
    /// * `bool` - `true` if the key exists, `false` otherwise
    pub fn contains_key(&self, key: &str) -> bool {
        let read_txn = match self.db.begin_read() {
            Ok(txn) => txn,
            Err(_) => return false,
        };

        let table = match read_txn.open_table(CACHE_TABLE) {
            Ok(t) => t,
            Err(_) => return false,
        };

        matches!(table.get(key), Ok(Some(_)))
    }

    /// Removes a key from the cache.
    ///
    /// # Arguments
    /// * `key` - The cache key to remove
    ///
    /// # Returns
    /// * `Result<()>` - Success, or an error if removal fails
    pub fn remove(&self, key: impl AsRef<str>) -> Result<()> {
        let write_txn = self.db.begin_write()?;

        {
            let mut table = write_txn.open_table(CACHE_TABLE)?;
            table.remove(key.as_ref())?;
        }

        write_txn.commit()?;

        Ok(())
    }

    /// Returns the number of entries in the cache.
    ///
    /// # Returns
    /// * `Result<u64>` - The count of entries, or an error if the operation fails
    pub fn len(&self) -> Result<u64> {
        let read_txn = self.db.begin_read()?;
        let table = read_txn.open_table(CACHE_TABLE)?;
        let leng = table.len()?;
        Ok(leng)
    }

    /// Checks whether the cache is empty.
    ///
    /// # Returns
    /// * `Result<bool>` - `true` if empty, `false` otherwise, or an error if check fails
    pub fn is_empty(&self) -> Result<bool> {
        let read_txn = self.db.begin_read()?;
        let table = read_txn.open_table(CACHE_TABLE)?;
        let empty = table.is_empty()?;
        Ok(empty)
    }
}
