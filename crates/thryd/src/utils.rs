//! Internal utility functions for the Thryd system.
//!
//! This module provides timestamp generation, HTTP header construction,
//! and other low-level utilities used across the crate.
//!
//! # Internal Usage
//!
//! - [`current_timestamp()`] - Used by [`crate::tracker`] for sliding window rate limiting
//! - [`build_headers()`] - Used by providers to construct authenticated HTTP headers

use crate::{ModelName, ProviderName, SEPARATE, ThrydError};
use http::header::AUTHORIZATION;
use http::{HeaderMap, HeaderValue};
use secrecy::{ExposeSecret, SecretString};
use std::time::{SystemTime, UNIX_EPOCH};

/// Timestamp type representing milliseconds since Unix epoch.
///
/// Used throughout the crate for sliding window rate limit calculations.
/// The timestamp is in milliseconds to provide fine-grained time tracking.
pub type TimeStamp = u128;

/// Returns the current timestamp in milliseconds since Unix epoch.
///
/// Used for tracking usage in sliding window buckets for RPM/TPM quota management.
///
/// # See Also
///
/// See [`crate::tracker`] for how timestamps are used in rate limiting.
pub(crate) fn current_timestamp() -> TimeStamp {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards")
        .as_millis()
}
/// Parse a deployment identifier into provider and model names.
///
/// # Arguments
/// * `identifier` - String in `"{provider}{SEPARATE}{model}"` format
///
/// # Returns
/// * `Ok((ProviderName, ModelName))` on successful parse
/// * `Err(ThrydError::Router)` if the format is invalid
pub fn analyze_identifier(identifier: String) -> crate::Result<(ProviderName, ModelName)> {
    identifier
        .split_once(SEPARATE)
        .ok_or_else(|| ThrydError::Router(format!("Invalid identifier `{}`", identifier)))
        .map(|(provider_name, model_name)| (provider_name.to_string(), model_name.to_string()))
}
/// Builds HTTP headers with Bearer token authorization.
///
/// Creates an authorization header in the format `Bearer <api_key>`.
/// The authorization value is marked as sensitive so it won't be logged.
///
/// # Arguments
///
/// * `key` - The API key secret string
///
/// # Returns
///
/// A [`HeaderMap`] containing the `Authorization: Bearer <key>` header.
///
/// # Errors
///
/// Returns [`crate::ThrydError::InvalidHeader`] if the formatted header value is invalid.
///
/// # Example
///
/// ```
/// use secrecy::SecretString;
/// use thryd::utils::build_headers;
///
/// # fn demo() -> crate::Result<()> {
/// let api_key = SecretString::from("sk-abc123".to_string());
/// let headers = build_headers(&api_key)?;
/// assert!(headers.contains_key(http::header::AUTHORIZATION));
/// # Ok(())
/// # }
/// ```
pub(crate) fn build_headers(key: &SecretString) -> crate::Result<HeaderMap> {
    let mut h = HeaderMap::new();

    let mut auth_header =
        HeaderValue::from_str(format!("Bearer {}", key.expose_secret()).as_str())?;

    auth_header.set_sensitive(true);

    h.insert(AUTHORIZATION, auth_header);
    Ok(h)
}
