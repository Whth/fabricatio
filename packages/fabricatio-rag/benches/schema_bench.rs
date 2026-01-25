// benches/schema_bench.rs
use criterion::{Bencher, Criterion, criterion_group, criterion_main};
use lancedb::arrow::arrow_schema::{DataType, Field, Schema, SchemaRef, TimeUnit};
use std::hint::black_box;
use std::sync::Arc;

use fabricatio_rag::constants::*;
use fabricatio_rag::schema::schema_of;

// --- Uncached version (the original function, but ensure it's pub or accessible) ---
fn schema_of_plain(ndim: i32) -> SchemaRef {
    Arc::new(Schema::new(vec![
        Field::new(ID_FIELD_NAME, DataType::Utf8View, false),
        Field::new(
            TIMESTAMP_FIELD_NAME,
            DataType::Time64(TimeUnit::Millisecond),
            false,
        ),
        Field::new_fixed_size_list(
            VECTOR_FIELD_NAME,
            Field::new(VECTOR_DIM_FIELD_NAME, DataType::Float64, false),
            ndim,
            false,
        ),
        Field::new(CONTENT_FIELD_NAME, DataType::Utf8, false),
        Field::new(METADATA_FIELD_NAME, DataType::Utf8View, true),
    ]))
}

fn bench_cached(b: &mut Bencher) {
    b.iter(|| {
        let s = schema_of(black_box(768));
        black_box(s);
    });
}

fn bench_plain(b: &mut Bencher) {
    b.iter(|| {
        let s = schema_of_plain(black_box(768));
        black_box(s);
    });
}

fn criterion_benchmark(c: &mut Criterion) {
    c.bench_function("schema_of with cached", bench_cached);
    c.bench_function("schema_of plain", bench_plain);
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
