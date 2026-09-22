//! The retry policy.

use std::time::Duration;

use reqwest::header::{HeaderMap, RETRY_AFTER};

/// How the client retries rate limits, overloads, and transport failures.
///
/// The API asks for exponential backoff on `429` and `529`; the client honors a numeric
/// `Retry-After` header when the API sends one and falls back to this schedule otherwise. Since an
/// evaluation is read-only, retrying it is always safe.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RetryConfig {
    /// Total attempts, counting the first try; `1` disables retrying.
    pub max_attempts: u32,
    /// The delay before the first retry.
    pub initial_backoff: Duration,
    /// The ceiling for a single delay.
    pub max_backoff: Duration,
    /// The factor applied after each failed attempt.
    pub backoff_multiplier: u32,
}

impl RetryConfig {
    /// The delay to wait after `attempt` failed, where the first attempt is 1.
    pub fn backoff(&self, attempt: u32) -> Duration {
        let factor = self
            .backoff_multiplier
            .saturating_pow(attempt.saturating_sub(1));
        self.initial_backoff
            .saturating_mul(factor)
            .min(self.max_backoff)
    }
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts: 4,
            initial_backoff: Duration::from_millis(500),
            max_backoff: Duration::from_secs(8),
            backoff_multiplier: 2,
        }
    }
}

/// The delay a `Retry-After` header asks for, when it carries a number of seconds.
///
/// The header may also carry an HTTP date, which this client does not parse: the caller falls back
/// to its own backoff schedule then.
pub(crate) fn retry_after(headers: &HeaderMap) -> Option<Duration> {
    headers
        .get(RETRY_AFTER)?
        .to_str()
        .ok()?
        .trim()
        .parse::<u64>()
        .ok()
        .map(Duration::from_secs)
}
