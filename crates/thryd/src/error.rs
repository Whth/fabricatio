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
}


pub type Result<T> = std::result::Result<T, ThrydError>;