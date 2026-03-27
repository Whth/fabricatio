use crate::Result;
use crate::utils::{TimeStamp, current_timestamp};
use redb::{Database, ReadableDatabase, ReadableTableMetadata, TableDefinition, TypeName, Value};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use std::fmt::Debug;

use std::path::Path;
use std::sync::Arc;

const CACHE_TABLE: TableDefinition<&str, CacheValue> = TableDefinition::new("cache");

#[derive(Debug, Default, Deserialize, Serialize)]
struct CacheValue {
    timestamp: TimeStamp,
    access_count: u64,
    data: Vec<u8>,
}

impl CacheValue {
    fn access_data<T: DeserializeOwned>(&self) -> Result<T> {
        let v = postcard::from_bytes(&self.data)?;
        Ok(v)
    }

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

impl Value for CacheValue {
    type SelfType<'a> = CacheValue;
    type AsBytes<'a> = Vec<u8>;

    fn fixed_width() -> Option<usize> {
        None
    }

    fn from_bytes<'a>(data: &'a [u8]) -> Self::SelfType<'a>
    where
        Self: 'a,
    {
        postcard::from_bytes::<CacheValue>(data).expect("Failed to deserialize cache value")
    }

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

/// Persistent cache using redb
#[derive(Clone)]
pub struct PersistentCache {
    db: Arc<Database>,
}

impl PersistentCache {
    /// Open or create a persistent cache at the given path
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

    /// Get a value from cache
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

    /// Get a deserialized value
    pub fn get_de<T: DeserializeOwned + Clone>(&self, key: &str) -> Option<T> {
        self.get(key)?.access_data::<T>().ok()
    }

    /// Store a value in cache
    fn set(&self, key: impl AsRef<str>, value: CacheValue) -> Result<()> {
        let trx = self.db.begin_write()?;

        trx.open_table(CACHE_TABLE)?.insert(key.as_ref(), value)?;

        trx.commit()?;

        Ok(())
    }

    /// Store a serialized value
    pub fn set_ser<T: Serialize>(&self, key: impl AsRef<str>, value: &T) -> Result<()> {
        self.set(key, CacheValue::from_data(value)?)
    }

    /// Check if key exists
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

    /// Remove a key
    pub fn remove(&self, key: impl AsRef<str>) -> Result<()> {
        let write_txn = self.db.begin_write()?;

        {
            let mut table = write_txn.open_table(CACHE_TABLE)?;
            table.remove(key.as_ref())?;
        }

        write_txn.commit()?;

        Ok(())
    }

    pub fn len(&self) -> Result<u64> {
        let read_txn = self.db.begin_read()?;
        let table = read_txn.open_table(CACHE_TABLE)?;
        let leng = table.len()?;
        Ok(leng)
    }

    pub fn is_empty(&self) -> Result<bool> {
        let read_txn = self.db.begin_read()?;
        let table = read_txn.open_table(CACHE_TABLE)?;
        let empty = table.is_empty()?;
        Ok(empty)
    }
}
