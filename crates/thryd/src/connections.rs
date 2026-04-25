use crate::{DEFAULT_MAX_CAPACITY, DEFAULT_TTL_SECS};
use moka::sync::Cache;
use once_cell::sync::Lazy;
use reqwest::Client;
use std::sync::Arc;
use std::time::Duration;
use url::Url;

/// A reusable `reqwest::Client` wrapped in an `Arc` for shared access.
///
/// `ClientEntry` is an alias for `Arc<Client>`, allowing the HTTP client
/// to be shared across multiple concurrent requests without cloning.
/// The `Arc` wrapper enables cheap cloning; multiple references share
/// the same underlying client and its connection pool.
///
/// # Example
/// ```rust
/// use thryd::connections::ClientEntry;
/// use reqwest::Client;
/// use std::sync::Arc;
///
/// // Create a new client entry
/// let client: ClientEntry = Arc::new(Client::new());
///
/// // Clone to share across threads
/// let client_clone = client.clone();
/// ```
pub type ClientEntry = Arc<Client>;

/// A global connection pool for HTTP clients, keyed by API endpoint base URL.
///
/// `CONNECTIONS_POOL` is a process-wide lazy-initialized cache that maintains
/// reusable HTTP clients for different API endpoints. Using a pool avoids the
/// overhead of creating new TCP connections and TLS handshakes for each request.
///
/// # How It Works
/// - **Lazy Initialization**: The pool is created on first access via `once_cell::sync::Lazy`
/// - **URL-keyed**: Each unique base URL gets its own `Client` instance
/// - **moka Cache**: Uses moka for thread-safe, evicting cache with TTL and capacity limits
/// - **Auto-eviction**: Entries expire after `DEFAULT_TTL_SECS` (1 hour) of inactivity;
///   when capacity exceeds `DEFAULT_MAX_CAPACITY` (100), LRU entries are evicted
///
/// # Connection Reuse
/// `reqwest::Client` maintains an internal connection pool. By reusing the same
/// `Client` instance for the same URL, subsequent requests can reuse:
/// - TCP connections (persistent connections)
/// - TLS session tickets (faster TLS handshake)
/// - HTTP/2 streams (for h2-enabled endpoints)
///
/// # Configuration
/// - **Max Capacity**: `DEFAULT_MAX_CAPACITY` (100 clients max)
/// - **TTL**: `DEFAULT_TTL_SECS` (3600 seconds = 1 hour idle time)
/// - **Key**: Base URL (`Url` type from the `url` crate)
///
/// # Example
/// ```rust
/// use thryd::connections::CONNECTIONS_POOL;
/// use url::Url;
///
/// // Get or create a client for an API endpoint
/// let url = Url::parse("https://api.openai.com").unwrap();
///
/// // The pool is lazy; first access creates the Cache
/// // Subsequent accesses with the same URL return the cached client
/// let client = CONNECTIONS_POOL.get(&url);
/// ```
pub(crate) static CONNECTIONS_POOL: Lazy<Cache<Url, ClientEntry>> = Lazy::new(|| {
    Cache::builder()
        .time_to_idle(Duration::from_secs(DEFAULT_TTL_SECS))
        .max_capacity(DEFAULT_MAX_CAPACITY)
        .build()
});
