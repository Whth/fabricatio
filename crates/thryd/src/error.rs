// src/error.rs
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ThrydError {
    #[error("Tracker error: {0}")]
    TrackerError(String),

    #[error("Invalid request: {0}")]
    InvalidRequest(String),

    #[error("Provider '{provider}' is not available: {reason}")]
    ProviderUnavailable { provider: String, reason: String },

    #[error("HTTP request failed: {0}")]
    HttpError(#[from] reqwest::Error),

    #[error("JSON serialization failed: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("No suitable provider found for model '{model}'")]
    NoProviderFound { model: String },

    #[error("Cache I/O error: {0}")]
    CacheIoError(#[from] std::io::Error),

    #[error("Configuration error: {0}")]
    ConfigurationError(String),

    #[error("API error: {0}")]
    ApiError(String),

    #[error("Rate limit exceeded. Try again in {wait_time_ms}ms")]
    RateLimitExceeded { wait_time_ms: u64 },

    #[error("Provider {0} returned an error response: {1}")]
    ProviderError(String, String),

    #[error("Missing required field: {0}")]
    MissingField(String),

    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),

    #[error("Operation timed out after {0}ms")]
    Timeout(u64),

    #[error("Authentication failed: {0}")]
    AuthenticationError(String),

    #[error("Model '{model}' not supported by provider '{provider}'")]
    ModelNotSupported { model: String, provider: String },

    #[error("Provider type parse error: {0}")]
    EnumParse(#[from] strum::ParseError),
}


pub type Result<T> = std::result::Result<T, ThrydError>;