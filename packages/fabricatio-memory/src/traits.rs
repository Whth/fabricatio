use crate::memory::{Memory, SCHEMA};
use serde_json::Value;
use tantivy::schema::document::{DeserializeError, DocumentDeserialize, DocumentDeserializer};
use tantivy::{Document, TantivyDocument};
impl DocumentDeserialize for Memory {
    fn deserialize<'de, D>(deserializer: D) -> Result<Self, DeserializeError>
    where
        D: DocumentDeserializer<'de>,
    {
        let o: String = TantivyDocument::deserialize(deserializer)?.to_json(&SCHEMA);

        let v = serde_json::from_str::<Value>(o.as_str()).expect("Failed to deserialize JSON");

        Ok(Memory {
            id: v
                .get("id")
                .expect("Field 'id' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_str()
                .expect("Field 'id' is not a u64")
                .to_string(),
            content: v
                .get("content")
                .expect("Field 'content' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_str()
                .expect("Field 'content' is not a string")
                .to_string(),
            timestamp: v
                .get("timestamp")
                .expect("Field 'timestamp' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_i64()
                .expect("Field 'timestamp' is not an i64"),
            importance: v
                .get("importance")
                .expect("Field 'importance' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_f64()
                .expect("Field 'importance' is not an f64"),
            tags: v
                .get("tags")
                .expect("Field 'tags' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_str()
                .expect("Field 'tags' is not a string") // Changed from to_string() to as_str() then split
                .split_whitespace()
                .map(|s| s.to_string())
                .collect(),
            access_count: v
                .get("access_count")
                .expect("Field 'access_count' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_u64()
                .expect("Field 'access_count' is not a u64"),
            last_accessed: v
                .get("last_accessed")
                .expect("Field 'last_accessed' missing")
                .as_array()
                .unwrap()
                .first()
                .unwrap()
                .as_i64()
                .expect("Field 'last_accessed' is not an i64"),
        })
    }
}
