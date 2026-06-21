//! Retry logic for transient network failures.
//!
//! Provides [`RetryConfig`] and [`retry_on_transient`] for automatic retries
//! with exponential backoff on network errors, timeouts, and upstream 429/5xx.

use crate::{Result, ThrydError};
use tracing::*;

/// Configuration for automatic retry on transient network failures.
///
/// When configured on a [`Router`](super::Router), failed requests will be retried with
/// exponential backoff for errors classified as transient (network failures,
/// timeouts, upstream 429/5xx).
///
/// # Example
///
/// ```ignore
/// use thryd::{Router, CompletionTag, RetryConfig};
///
/// let router = Router::<CompletionTag>::default()
///     .with_retry(RetryConfig {
///         max_retries: 3,
///         initial_backoff_ms: 500,
///         ..RetryConfig::default()
///     });
/// ```
#[derive(Debug, Clone)]
pub struct RetryConfig {
    /// Maximum number of retry attempts after the initial failure. `0` means no retries.
    pub max_retries: u32,
    /// Initial backoff duration in milliseconds before the first retry.
    pub initial_backoff_ms: u64,
    /// Cap on backoff duration in milliseconds.
    pub max_backoff_ms: u64,
    /// Multiplier applied to backoff after each retry (exponential backoff).
    pub backoff_multiplier: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            initial_backoff_ms: 1000,
            max_backoff_ms: 30_000,
            backoff_multiplier: 2.0,
        }
    }
}

/// Execute an async operation with retry on transient errors.
///
/// Retries on network failures, timeouts, and upstream 429/5xx errors.
/// Uses exponential backoff, respecting `RateLimitExceeded.wait_time_ms` as floor.
pub(crate) async fn retry_on_transient<F, Fut, T>(config: &RetryConfig, mut op: F) -> Result<T>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = Result<T>>,
{
    let mut attempt = 0u32;
    loop {
        match op().await {
            Ok(val) => return Ok(val),
            Err(e) if attempt < config.max_retries && is_transient(&e) => {
                attempt += 1;
                let base = (config.initial_backoff_ms as f64
                    * config.backoff_multiplier.powi(attempt as i32 - 1))
                .min(config.max_backoff_ms as f64) as u64;

                let wait_ms = match &e {
                    ThrydError::RateLimitExceeded { wait_time_ms } => base.max(*wait_time_ms),
                    _ => base,
                };

                warn!(
                    "Transient error (attempt {}/{}): {}. Retrying in {}ms",
                    attempt, config.max_retries, e, wait_ms
                );
                tokio::time::sleep(tokio::time::Duration::from_millis(wait_ms)).await;
            }
            Err(e) => return Err(e),
        }
    }
}

/// Returns `true` for errors caused by transient network/server conditions.
fn is_transient(e: &ThrydError) -> bool {
    match e {
        ThrydError::Reqwest(_)
        | ThrydError::Timeout(_)
        | ThrydError::RateLimitExceeded { .. }
        | ThrydError::SSE(_) => true,
        ThrydError::ApiError { status, .. } => *status == 429 || *status >= 500,
        _ => false,
    }
}
