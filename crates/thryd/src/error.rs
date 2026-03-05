use async_openai::error::OpenAIError;
use eventsource_stream::EventStreamError;
use reqwest::Error as ReqwestError;
use serde_json::Error as SerdeJsonError;
use std::env::VarError;
use std::io::Error as IoError;
use strum::ParseError as StrumParseError;
use thiserror::Error;
use url::ParseError;

/// Represents the unified error types for the Thryd system.
///
/// This enum consolidates various failure scenarios including network issues,
/// provider unavailability, configuration faults, and data validation errors.
#[derive(Error, Debug)]
pub enum ThrydError {
    /// Indicates that a specific provider is unavailable.
    #[error("Provider '{provider}' is not available: {reason}")]
    ProviderUnavailable {
        provider: String,
        reason: String,
    },

    /// Indicates that no suitable provider could be found for the requested model.
    #[error("No suitable provider found for model '{model}'")]
    NoProviderFound {
        model: String
    },

    /// Indicates that a specific model is not supported by the chosen provider.
    #[error("Model '{model}' is not supported by provider '{provider}'")]
    ModelNotSupported {
        model: String,
        provider: String,
    },

    #[error("Model {name} is not supported by provider: {msg}")]
    ClientError {
        name: String,
        msg: String,
    },

    /// Indicates that a provided header value is invalid.
    #[error("Invalid header: {0}")]
    InvalidHeader(#[from] http::header::InvalidHeaderValue),

    /// Indicates that the operation exceeded the allowed time limit.
    #[error("Operation timed out after {0}ms")]
    Timeout(u64),

    /// Indicates that the rate limit has been exceeded.
    #[error("Rate limit exceeded. Try again in {wait_time_ms}ms")]
    RateLimitExceeded {
        wait_time_ms: u64
    },

    /// Wraps external HTTP request errors.
    #[error("HTTP request failed: {0}")]
    Reqwest(#[from] ReqwestError),

    /// Wraps JSON serialization/deserialization errors.
    #[error("JSON processing failed: {0}")]
    Json(#[from] SerdeJsonError),

    /// Wraps file or cache I/O errors.
    #[error("Cache I/O error: {0}")]
    CacheIo(#[from] IoError),

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

    #[error("Internal error: {0}")]
    Internal(String),
}


pub type Result<T> = std::result::Result<T, ThrydError>;