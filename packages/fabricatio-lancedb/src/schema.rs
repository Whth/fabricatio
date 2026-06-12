use crate::constants::*;
use cached::macros::cached;
use lancedb::arrow::arrow_schema::*;
use std::sync::Arc;

/// Creates a new LanceDB schema for the given number of dimensions.
///
/// The schema includes fields for id, timestamp, vector, content, and metadata.
///
/// Args:
///     ndim: The number of dimensions for the vector field.
///
/// Returns:
///     A SchemaRef pointing to the created schema.
#[cached]
pub fn schema_of(ndim: i32) -> SchemaRef {
    Arc::new(Schema::new(vec![
        Field::new(ID_FIELD_NAME, DataType::Utf8, false),
        Field::new(
            TIMESTAMP_FIELD_NAME,
            DataType::Time64(TimeUnit::Microsecond),
            false,
        ),
        Field::new_fixed_size_list(
            VECTOR_FIELD_NAME,
            Field::new(VECTOR_DIM_FIELD_NAME, DataType::Float32, true),
            ndim,
            false,
        ),
        Field::new(CONTENT_FIELD_NAME, DataType::Utf8, false),
        Field::new(METADATA_FIELD_NAME, DataType::Utf8, true),
    ]))
}
