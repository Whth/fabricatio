use once_cell::sync::Lazy;
use tantivy::schema::{Field, INDEXED, STORED, Schema, TEXT};

pub static SCHEMA: Lazy<Schema> = Lazy::new(|| {
    let mut schema_builder = Schema::builder();

    schema_builder.add_u64_field("id", STORED | INDEXED);
    schema_builder.add_text_field("content", TEXT | STORED);
    schema_builder.add_text_field("tags", TEXT | STORED);
    schema_builder.add_i64_field("timestamp", STORED | INDEXED);
    schema_builder.add_f64_field("importance", STORED | INDEXED);
    schema_builder.add_u64_field("access_count", STORED | INDEXED);
    schema_builder.add_i64_field("last_accessed", STORED | INDEXED);

    schema_builder.build()
});
pub static FIELDS: Lazy<(Field, Field, Field, Field, Field, Field, Field)> = Lazy::new(|| {
    let id_field = SCHEMA.get_field("id").unwrap();
    let content_field = SCHEMA.get_field("content").unwrap();
    let tags_field = SCHEMA.get_field("tags").unwrap();
    let timestamp_field = SCHEMA.get_field("timestamp").unwrap();
    let importance_field = SCHEMA.get_field("importance").unwrap();
    let access_count_field = SCHEMA.get_field("access_count").unwrap();
    let last_accessed_field = SCHEMA.get_field("last_accessed").unwrap();

    (
        id_field,
        content_field,
        tags_field,
        timestamp_field,
        importance_field,
        access_count_field,
        last_accessed_field,
    )
});
