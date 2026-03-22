use redb::{Database, TableDefinition, ReadableTable, ReadableDatabase, Value, TypeName};
use serde::{Serialize, de::DeserializeOwned, Deserialize};
use std::path::Path;
use std::sync::Arc;

use crate::Result;

/// Define the schema for the cache table.
/// Key: &str, Value: &[u8]
/// This must be a static constant in redb.
const CACHE_TABLE: TableDefinition<&str, &[u8]> = TableDefinition::new("cache");

/// Persistent cache using redb
pub struct PersistentCache {
    db: Database,
}


impl PersistentCache {
    /// Open or create a persistent cache at the given path
    pub fn open(path: impl AsRef<Path>) -> std::io::Result<Self> {
        // Create or open the database file
        let db = Database::create(path.as_ref())
            .map_err(std::io::Error::other)?;

        // Ensure the table exists (redb requires tables to be defined before use)
        let write_txn = db.begin_write()
            .map_err(std::io::Error::other)?;
        {
            let _ = write_txn.open_table(CACHE_TABLE)
                .map_err(std::io::Error::other)?;
        }
        write_txn.commit()
            .map_err(std::io::Error::other)?;

        Ok(Self { db })
    }

    /// Get a value from cache
    pub fn get(&self, key: &str) -> Option<String> {
        let read_txn = self.db.begin_read().ok()?;
        let table = read_txn.open_table(CACHE_TABLE).ok()?;

        let value = table.get(key).ok()??;
        let bytes = value.value();

        String::from_utf8(bytes.to_vec()).ok()
    }

    /// Get a deserialized value
    pub fn get_de<T: DeserializeOwned + Clone>(&self, key: &str) -> Option<T> {
        self.get(key).and_then(|v| serde_json::from_str(&v).ok())
    }

    /// Store a value in cache
    pub fn set(&self, key: impl AsRef<str>, value: impl AsRef<str>) -> Result<()> {
        let key_str = key.as_ref();
        let value_bytes = value.as_ref().as_bytes();

        let write_txn = self.db.begin_write()
            ?;

        {
            let mut table = write_txn.open_table(CACHE_TABLE)
                ?;
            table.insert(key_str, value_bytes)
                ?;
        }

        write_txn.commit()
            ?;

        Ok(())
    }

    /// Store a serialized value
    pub fn set_ser<T: Serialize>(&self, key: &str, value: &T) -> Result<()> {
        let json = serde_json::to_string(value)?;
        self.set(key, json)
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
    pub fn remove(&self, key: &str) -> Result<()> {
        let write_txn = self.db.begin_write()
            ?;

        {
            let mut table = write_txn.open_table(CACHE_TABLE)
                ?;
            table.remove(key)
                ?;
        }

        write_txn.commit()
            ?;


        Ok(())
    }


    pub fn flush(&self) -> Result<usize> {
        unimplemented!()
    }
}

