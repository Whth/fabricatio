use once_cell::sync::Lazy;
use tantivy::schema::{FAST, Field, INDEXED, STORED, STRING, Schema, TEXT};

pub mod field_names {
    pub const UUID: &str = "uuid";
    pub const CONTENT: &str = "content";
    pub const TAGS: &str = "tags";
    pub const TIMESTAMP: &str = "timestamp";
    pub const IMPORTANCE: &str = "importance";
    pub const ACCESS_COUNT: &str = "access_count";
    pub const LAST_ACCESSED: &str = "last_accessed";
}

pub static MAX_IMPORTANCE_SCORE: u64 = 100;
pub static MAX_IMPORTANCE_SCORE_VARNAME: &str = "MAX_IMPORTANCE_SCORE";
pub static MIN_IMPORTANCE_SCORE: u64 = 0;
pub static MIN_IMPORTANCE_SCORE_VARNAME: &str = "MIN_IMPORTANCE_SCORE";
pub(crate) static MODULE_NAME: &str = concat!(env!("CARGO_CRATE_NAME"), ".rust");

pub static METADATA_FILE_NAME: &str = "meta.json";

pub static SCHEMA: Lazy<Schema> = Lazy::new(|| {
    let mut schema_builder = Schema::builder();

    schema_builder.add_text_field(field_names::UUID, STRING | STORED);
    schema_builder.add_text_field(field_names::CONTENT, TEXT | STORED);
    schema_builder.add_text_field(field_names::TAGS, STRING | STORED);
    schema_builder.add_i64_field(field_names::TIMESTAMP, INDEXED | FAST);
    schema_builder.add_u64_field(field_names::IMPORTANCE, INDEXED | FAST);
    schema_builder.add_u64_field(field_names::ACCESS_COUNT, INDEXED | FAST);
    schema_builder.add_i64_field(field_names::LAST_ACCESSED, INDEXED | FAST);

    schema_builder.build()
});

pub struct MemoryFields {
    pub uuid: Field,
    pub content: Field,
    pub tags: Field,
    pub timestamp: Field,
    pub importance: Field,
    pub access_count: Field,
    pub last_accessed: Field,
}

pub static FIELDS: Lazy<MemoryFields> = Lazy::new(|| MemoryFields {
    uuid: SCHEMA.get_field(field_names::UUID).unwrap(),
    content: SCHEMA.get_field(field_names::CONTENT).unwrap(),
    tags: SCHEMA.get_field(field_names::TAGS).unwrap(),
    timestamp: SCHEMA.get_field(field_names::TIMESTAMP).unwrap(),
    importance: SCHEMA.get_field(field_names::IMPORTANCE).unwrap(),
    access_count: SCHEMA.get_field(field_names::ACCESS_COUNT).unwrap(),
    last_accessed: SCHEMA.get_field(field_names::LAST_ACCESSED).unwrap(),
});
