use crate::constants::{FIELDS, SCHEMA};
use crate::memory::Memory;
use fabricatio_logger::trace;
use tantivy::schema::document::{DeserializeError, DocumentDeserialize, DocumentDeserializer};
use tantivy::schema::Value;
use tantivy::{Document, TantivyDocument};

impl DocumentDeserialize for Memory {
    fn deserialize<'de, D>(deserializer: D) -> Result<Self, DeserializeError>
    where
        D: DocumentDeserializer<'de>,
    {
        let doc = TantivyDocument::deserialize(deserializer)?;

        trace!("Retrieved memory: {}", doc.to_json(&SCHEMA));

        Ok(Memory {
            uuid: doc
                .get_first(FIELDS.uuid)
                .expect("Field 'uuid' missing")
                .as_str()
                .expect("Field 'uuid' is not a string")
                .to_string(),
            content: doc
                .get_first(FIELDS.content)
                .expect("Field 'content' missing")
                .as_str()
                .expect("Field 'content' is not a string")
                .to_string(),
            timestamp: doc
                .get_first(FIELDS.timestamp)
                .expect("Field 'timestamp' missing")
                .as_i64()
                .expect("Field 'timestamp' is not an i64"),
            importance: doc
                .get_first(FIELDS.importance)
                .expect("Field 'importance' missing")
                .as_u64()
                .expect("Field 'importance' is not an u64"),
            tags: doc
                .get_all(FIELDS.tags)
                .map(|seq| {
                    seq.as_str()
                        .expect("Field 'tags' is not a string")
                        .to_string()
                })
                .collect(),
            access_count: doc
                .get_first(FIELDS.access_count)
                .expect("Field 'access_count' missing")
                .as_u64()
                .expect("Field 'access_count' is not a u64"),
            last_accessed: doc
                .get_first(FIELDS.last_accessed)
                .expect("Field 'last_accessed' missing")
                .as_i64()
                .expect("Field 'last_accessed' is not an i64"),
        })
    }
}
