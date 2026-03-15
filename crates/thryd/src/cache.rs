use serde::Serialize;
use std::path::Path;

use crate::{Result, ThrydError};

/// Persistent cache using sled
pub struct PersistentCache {
    db: sled::Db,
}

impl PersistentCache {
    /// Open or create a persistent cache at the given path
    pub fn open(path: impl AsRef<Path>) -> std::io::Result<Self> {
        let db = sled::open(path)?;

        Ok(Self { db })
    }


    /// Get a value from cache
    pub fn get(&self, key: &str) -> Option<String> {
        self.db.get(key).ok().flatten().and_then(|v| {
            String::from_utf8(v.to_vec()).ok()
        })
    }

    /// Get a deserialized value
    pub fn get_de<T: serde::de::DeserializeOwned + Clone>(&self, key: &str) -> Option<T> {
        self.get(key).and_then(|v| serde_json::from_str(&v).ok())
    }

    /// Store a value in cache
    pub fn set(&self, key: impl AsRef<str>, value: impl AsRef<str>) -> Result<()> {
        let key = key.as_ref();
        let value = value.as_ref().as_bytes().to_vec();
        self.db.insert(key, value)?;
        Ok(())
    }

    /// Store a serialized value
    pub fn set_ser<T: Serialize>(&self, key: &str, value: &T) -> Result<()> {
        let json = serde_json::to_string(value)?;
        self.set(key, json)?;
        Ok(())
    }

    /// Check if key exists
    pub fn contains_key(&self, key: &str) -> bool {
        self.db.contains_key(key).unwrap_or(false)
    }

    /// Remove a key
    pub fn remove(&self, key: &str) -> Result<()> {
        self.db.remove(key)?;
        Ok(())
    }

    /// Clear all entries
    pub fn clear(&self) -> Result<()> {
        self.db.clear()?;
        Ok(())
    }

    /// Flush pending writes to disk
    pub async fn flush(&self) -> Result<usize> {
        self.db.flush_async().await.map_err(
            ThrydError::Sled
        )
    }
}
