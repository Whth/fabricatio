//! Error types for the Thryd system.
//!
//! This module provides the unified [`ThrydError`] enum that consolidates all failure
//! scenarios across providers, routing, caching, and network operations.
//!
//! # Error Categories
//!
//! - **Provider Errors**: Provider unavailability, API key issues, model support
//! - **Router Errors**: Missing deployments, invalid group names, routing failures
//! - **Rate Limit Errors**: RPM/TPM quota exhaustion with suggested wait times
//! - **Cache Errors**: Database I/O failures (redb, postcard serialization)
//! - **Network Errors**: HTTP request failures, timeouts, SSE stream issues
//! - **Parse Errors**: JSON processing, URL parsing, enum type conversion
//!
//! # Example
//!
//! ```rust
//! use thryd::{ThrydError, Result};
//!
//! async fn handle_error() -> Result<String> {
//!     Err(ThrydError::RateLimitExceeded { wait_time_ms: 5000 })
//! }
//! ```
//!
//! All variants implement [`std::error::Error`] and can be matched pattern-matched
//! for error handling. The [`ThrydError::RateLimitExceeded`] variant is particularly
//! useful for implementing retry logic with backoff.

use async_openai::error::OpenAIError;
use eventsource_stream::EventStreamError;
use reqwest::Error as ReqwestError;
use serde_json::Error as SerdeJsonError;
use std::env::VarError;
use strum::ParseError as StrumParseError;
use thiserror::Error;
use url::ParseError;

/// Represents the unified error types for the Thryd system.
///
/// This enum consolidates various failure scenarios including network issues,
/// provider unavailability, configuration faults, and data validation errors.
///
/// # Variants
///
/// | Category | Variant | Description |
/// |----------|---------|-------------|
/// | Provider | [`ThrydError::ProviderUnavailable`] | Specific provider is down |
/// | Provider | [`ThrydError::NoProviderFound`] | No provider for requested model |
/// | Provider | [`ThrydError::ModelNotSupported`] | Model not supported by provider |
/// | Router | [`ThrydError::Router`] | General routing failures |
/// | Rate Limit | [`ThrydError::RateLimitExceeded`] | RPM/TPM quota exceeded |
/// | Network | [`ThrydError::Reqwest`] | HTTP request failures |
/// | Network | [`ThrydError::Timeout`] | Operation timed out |
/// | Cache | [`ThrydError::Redb`], [`ThrydError::RedbTable`], etc. | Database errors |
/// | Parse | [`ThrydError::Json`] | JSON serialization errors |
///
/// # Example
///
/// ```rust
/// use thryd::{ThrydError, Result, Router, CompletionTag};
///
/// # async fn demo() -> Result<()> {
/// let mut router = Router::<CompletionTag>::default();
///
/// match router.invoke("nonexistent".into(), /* request */).await {
///     Ok(response) => println!("Got: {response}"),
///     Err(ThrydError::Router(msg)) => {
///         eprintln!("Router error - likely no deployments: {msg}");
///     }
///     Err(ThrydError::RateLimitExceeded { wait_time_ms }) => {
///         eprintln!("Rate limited. Wait {wait_time_ms}ms before retry");
///     }
///     Err(e) => eprintln!("Other error: {e}"),
/// }
/// # Ok(())
/// # }
/// ```
#[derive(Error, Debug)]
pub enum ThrydError {
    /// Indicates that a specific provider is unavailable.
    ///
    /// This typically occurs when a provider service is down or unreachable.
    /// The `reason` field provides details about the unavailability.
    #[error("Provider '{provider}' is not available: {reason}")]
    ProviderUnavailable { provider: String, reason: String },

    /// Provider creation failed due to missing or invalid configuration.
    ///
    /// Common causes: missing API key, invalid endpoint URL, missing provider name.
    #[error("Provider create error: {0}")]
    ProviderCreate(String),

    /// Indicates that no suitable provider could be found for the requested model.
    ///
    /// This happens when an identifier like `"openai::gpt-4"` is used but no
    /// provider with that name has been added to the router.
    #[error("No suitable provider found for model '{model}'")]
    NoProviderFound { model: String },

    /// Indicates that a specific model is not supported by the chosen provider.
    ///
    /// Some providers only support specific models. Check provider documentation
    /// for supported model list.
    #[error("Model '{model}' is not supported by provider '{provider}'")]
    ModelNotSupported { model: String, provider: String },

    /// Client-side error when constructing requests or validating configuration.
    ///
    /// Contains the model/provider name and a descriptive message.
    #[error("Model {name} is not supported by provider: {msg}")]
    ClientError { name: String, msg: String },

    /// Indicates that a provided header value is invalid.
    #[error("Invalid header: {0}")]
    InvalidHeader(#[from] http::header::InvalidHeaderValue),

    /// Indicates that the operation exceeded the allowed time limit.
    ///
    /// The value is the timeout duration in milliseconds.
    #[error("Operation timed out after {0}ms")]
    Timeout(u64),

    /// Indicates that the rate limit has been exceeded.
    ///
    /// Contains `wait_time_ms` indicating how long to wait before retry.
    /// Use this for implementing retry logic with exponential backoff.
    #[error("Rate limit exceeded. Try again in {wait_time_ms}ms")]
    RateLimitExceeded { wait_time_ms: u64 },

    /// Wraps external HTTP request errors.
    #[error("HTTP request failed: {0}")]
    Reqwest(#[from] ReqwestError),

    /// Wraps JSON serialization/deserialization errors.
    #[error("JSON processing failed: {0}")]
    Json(#[from] SerdeJsonError),

    /// Wraps file or cache I/O errors.
    #[error("Postcard error: {0}")]
    PostCard(#[from] postcard::Error),

    #[error("Redb error: {0}")]
    Redb(#[from] redb::Error),

    #[error("Redb table error: {0}")]
    RedbTable(#[from] redb::TableError),

    #[error("Redb transaction error: {0}")]
    RedbTransaction(#[from] redb::TransactionError),

    #[error("Redb storage error: {0}")]
    RedbStorage(#[from] redb::StorageError),
    #[error("Redb commit error: {0}")]
    RedbCommit(#[from] redb::CommitError),
    #[error("Redb database error: {0}")]
    RedbDataBase(#[from] redb::DatabaseError),

    /// Wraps environment variable retrieval errors.
    #[error("Environment variable error: {0}")]
    EnvVar(#[from] VarError),

    /// Wraps URL parsing errors.
    #[error("URL parse error: {0}")]
    UrlParse(#[from] ParseError),

    #[error("Http error: {0}")]
    Http(#[from] http::Error),

    /// Wraps enum parsing errors (e.g., provider type).
    #[error("Type parse error: {0}")]
    EnumParse(#[from] StrumParseError),

    /// Wraps Server-Sent Events (SSE) stream errors.
    #[error("SSE stream error: {0}")]
    SSE(#[from] EventStreamError<ReqwestError>),

    #[error("Openai error: {0}")]
    Openai(#[from] OpenAIError),

    #[error("Router error: {0}")]
    Router(String),

    #[error("Internal error: {0}")]
    Internal(String),
}

pub type Result<T> = std::result::Result<T, ThrydError>;
