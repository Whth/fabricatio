use crate::{DEFAULT_MAX_CAPACITY, DEFAULT_TTL_SECS};
use moka::sync::Cache;
use once_cell::sync::Lazy;
use reqwest::Client;
use std::sync::Arc;
use std::time::Duration;
use url::Url;

pub type ClientEntry = Arc<Client>;

/// Global connection pool
pub(crate) static CONNECTIONS_POOL: Lazy<Cache<Url, ClientEntry>> = Lazy::new(|| {
    Cache::builder()
        .time_to_idle(Duration::from_secs(DEFAULT_TTL_SECS))
        .max_capacity(DEFAULT_MAX_CAPACITY)
        .build()
});
