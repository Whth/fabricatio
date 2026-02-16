use async_openai::config::Config;
use async_openai::Client;
use moka::sync::Cache;
use once_cell::sync::OnceCell;
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use secrecy::{ExposeSecret, SecretString};
use std::sync::Arc;
use std::time::Duration;

/// Default cache configuration
const DEFAULT_MAX_CAPACITY: u64 = 100;
const DEFAULT_TTL_SECS: u64 = 3600;

#[derive(Debug, Clone)]
pub struct ClientConfig {
    api_base: String,
    api_key: SecretString,
    headers: HeaderMap,
}

impl ClientConfig {
    /// Create a new client configuration
    pub fn new(api_base: impl Into<String>, api_key: SecretString) -> Self {
        Self {
            api_base: api_base.into(),
            api_key,
            headers: HeaderMap::new(),
        }
    }

    /// Create with custom headers
    pub fn with_headers(mut self, headers: HeaderMap) -> Self {
        self.headers = headers;
        self
    }

    /// Get API base URL
    pub fn api_base(&self) -> &str {
        &self.api_base
    }

    /// Get API key (exposed)
    pub fn api_key(&self) -> &SecretString {
        &self.api_key
    }

    /// Get headers
    pub fn headers(&self) -> &HeaderMap {
        &self.headers
    }
}

impl Config for ClientConfig {
    fn headers(&self) -> HeaderMap {
        let mut headers = self.headers.clone();

        headers.insert(
            AUTHORIZATION,
            HeaderValue::from_str(&format!("Bearer {}", self.api_key.expose_secret()))
                .expect("Invalid API key"),
        );

        headers
    }

    fn url(&self, path: &str) -> String {
        let base = self.api_base.trim_end_matches('/');
        format!("{}{}", base, path)
    }

    fn query(&self) -> Vec<(&str, &str)> {
        Vec::new()
    }

    fn api_base(&self) -> &str {
        &self.api_base
    }

    fn api_key(&self) -> &SecretString {
        &self.api_key
    }
}

pub type ClientEntry = Arc<Client<ClientConfig>>;

/// Global connection pool
static CONNECTIONS_POOL: OnceCell<Cache<String, ClientEntry>> = OnceCell::new();

/// Get or initialize the global connection pool
pub fn get_connection_pool() -> &'static Cache<String, ClientEntry> {
    CONNECTIONS_POOL.get_or_init(|| {
        Cache::builder()
            .max_capacity(DEFAULT_MAX_CAPACITY)
            .time_to_live(Duration::from_secs(DEFAULT_TTL_SECS))
            .build()
    })
}

/// Get a client from the pool, creating if necessary
pub fn get_client(config: &ClientConfig) -> ClientEntry {
    let pool = get_connection_pool();
    let key = config.url("/");

    pool.get_with(key, || {
        Arc::new(Client::with_config(config.clone()))
    })
}

/// Create a new OpenAI-compatible client
pub fn create_openai_client(api_key: SecretString) -> ClientEntry {
    let config = ClientConfig::new("https://api.openai.com/v1", api_key);
    get_client(&config)
}

/// Create a client with custom base URL
pub fn create_client_with_base(api_base: String, api_key: SecretString) -> ClientEntry {
    let config = ClientConfig::new(api_base, api_key);
    get_client(&config)
}

/// Clear all cached connections
pub fn clear_connections() {
    if let Some(pool) = CONNECTIONS_POOL.get() {
        pool.invalidate_all();
    }
}

/// Get connection pool stats
pub fn connection_stats() -> ConnectionStats {
    let pool = get_connection_pool();
    ConnectionStats {
        entry_count: pool.entry_count(),
        max_capacity: DEFAULT_MAX_CAPACITY,
    }
}



/// Connection pool statistics
#[derive(Debug, Clone)]
pub struct ConnectionStats {
    pub entry_count: u64,
    pub max_capacity: u64,
}
