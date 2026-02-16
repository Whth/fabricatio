use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::Duration;

/// Cache configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheConfig {
    /// Maximum number of entries
    pub max_capacity: u64,
    /// Time to live for cache entries
    pub time_to_live: Duration,
    /// Path for persistent storage
    pub persist_path: Option<PathBuf>,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            max_capacity: 10_000,
            time_to_live: Duration::from_secs(60 * 60 * 24), // 24 hours
            persist_path: None,
        }
    }
}

/// Persistent cache using sled
pub struct PersistentCache {
    db: sled::Db,
}

impl PersistentCache {
    /// Open or create a persistent cache at the given path
    pub fn open(path: impl Into<PathBuf>) -> std::io::Result<Self> {
        let path = path.into();
        let db = sled::open(&path)?;
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
    pub fn set(&self, key: impl AsRef<str>, value: impl AsRef<str>) {
        let key = key.as_ref();
        let value = value.as_ref().as_bytes().to_vec();
        let _ = self.db.insert(key, value);
    }

    /// Store a serialized value
    pub fn set_ser<T: Serialize>(&self, key: &str, value: &T) -> serde_json::Result<()> {
        let json = serde_json::to_string(value)?;
        self.set(key, json);
        Ok(())
    }

    /// Check if key exists
    pub fn contains_key(&self, key: &str) -> bool {
        self.db.contains_key(key).unwrap_or(false)
    }

    /// Remove a key
    pub fn remove(&self, key: &str) {
        let _ = self.db.remove(key);
    }

    /// Clear all entries
    pub fn clear(&self) {
        let _ = self.db.clear();
    }

    /// Flush pending writes to disk
    pub fn flush(&self) -> std::io::Result<()> {
        match self.db.flush() {
            Ok(_) => Ok(()),
            Err(e) => Err(std::io::Error::other(e.to_string())),
        }
    }

    /// Generate cache key from request content
    pub fn generate_key(prompt: &str, model: &str) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        prompt.hash(&mut hasher);
        model.hash(&mut hasher);
        format!("thryd:{}:{:x}", model, hasher.finish())
    }
}

/// Cache statistics
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CacheStats {
    pub hits: u64,
    pub misses: u64,
    pub size: u64,
}

impl CacheStats {
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f64 / total as f64
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_config_default() {
        let config = CacheConfig::default();
        assert_eq!(config.max_capacity, 10_000);
        assert!(config.persist_path.is_none());
    }

    #[test]
    fn test_generate_key() {
        let key1 = PersistentCache::generate_key("hello", "gpt-4");
        let key2 = PersistentCache::generate_key("hello", "gpt-4");
        let key3 = PersistentCache::generate_key("world", "gpt-4");
        
        // Same input should produce same key
        assert_eq!(key1, key2);
        // Different input should produce different key
        assert_ne!(key1, key3);
        // Key should start with prefix
        assert!(key1.starts_with("thryd:"));
    }

    #[test]
    fn test_cache_stats() {
        let stats = CacheStats::default();
        assert_eq!(stats.hits, 0);
        assert_eq!(stats.misses, 0);
        assert_eq!(stats.hit_rate(), 0.0);

        let mut stats = CacheStats {
            hits: 5,
            misses: 5,
            size: 10,
        };
        assert_eq!(stats.hit_rate(), 0.5);
    }
}
