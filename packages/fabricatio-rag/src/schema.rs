use crate::constants::*;
use lancedb::arrow::arrow_schema::{DataType, Field, Schema, TimeUnit};


/// Create a new schema for the given number of dimensions.
pub(crate) fn schema_of(ndim: i32) -> Schema {
    Schema::new(
        vec![
            Field::new(ID_FIELD_NAME, DataType::Utf8View, false),
            Field::new(TIMESTAMP_FIELD_NAME, DataType::Time64(TimeUnit::Millisecond), false),
            Field::new_fixed_size_list(VECTOR_FIELD_NAME, Field::new(VECTOR_DIM_FIELD_NAME, DataType::Float64, false), ndim, false),
            Field::new(CONTENT_FIELD_NAME, DataType::Utf8, false),
            Field::new(METADATA_FIELD_NAME, DataType::Utf8View, false)
        ]
    )
}


