//! The error taxonomy.

use std::time::Duration;

use reqwest::StatusCode;
use thiserror::Error;

/// A request the API would reject with `422 Unprocessable Entity`.
///
/// Raised while questions and requests are built, so a malformed request never costs a round trip.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
#[error("{reason}")]
pub struct InvalidRequest {
    reason: String,
}

impl InvalidRequest {
    pub(crate) fn new(reason: impl Into<String>) -> Self {
        Self {
            reason: reason.into(),
        }
    }

    /// Why the request is invalid.
    pub fn reason(&self) -> &str {
        &self.reason
    }
}

/// Everything that can go wrong while calling System One.
#[derive(Debug, Error)]
pub enum Error {
    /// The request breaks the API's own constraints, so it was not sent.
    #[error(transparent)]
    Invalid(#[from] InvalidRequest),

    /// No API key was available.
    #[error("no API key: pass one to the client, or set the JEVLIN_API_KEY environment variable")]
    MissingApiKey,

    /// The base URL is not a URL.
    #[error("invalid base URL `{url}`: {reason}")]
    InvalidBaseUrl {
        /// The URL as given.
        url: String,
        /// Why it could not be parsed.
        reason: String,
    },

    /// `401 Unauthorized`: the API key is missing or invalid.
    #[error("authentication failed: check the API key (401)")]
    Unauthorized,

    /// `422 Unprocessable Entity`: the API rejected the request body.
    #[error("the API rejected the request body (422): {detail}")]
    Unprocessable {
        /// The body the API returned, which names the offending field.
        detail: String,
    },

    /// `429 Too Many Requests`: the rate limit is exhausted.
    #[error("rate limited by the API (429)")]
    RateLimited {
        /// The delay the API asked for, when it sent one.
        retry_after: Option<Duration>,
    },

    /// `529 Overloaded`: the API is temporarily overloaded.
    #[error("the API is overloaded (529)")]
    Overloaded {
        /// The delay the API asked for, when it sent one.
        retry_after: Option<Duration>,
    },

    /// Any other status.
    #[error("unexpected response ({status}): {body}")]
    Unexpected {
        /// The HTTP status code.
        status: u16,
        /// The body the API returned.
        body: String,
    },

    /// The API answered the request but left a question unanswered.
    #[error("the API returned no answer for question `{id}`")]
    MissingAnswer {
        /// The id that went unanswered.
        id: String,
    },

    /// The HTTP layer failed: building the client, connecting, TLS, timeouts, or reading the body.
    #[error(transparent)]
    Transport(#[from] reqwest::Error),

    /// A response body did not match the shape the API documents.
    #[error(transparent)]
    Decode(#[from] serde_json::Error),
}

impl Error {
    /// Maps a non-success status onto the taxonomy.
    pub(crate) fn from_response(
        status: StatusCode,
        retry_after: Option<Duration>,
        body: String,
    ) -> Self {
        match status.as_u16() {
            401 => Self::Unauthorized,
            422 => Self::Unprocessable { detail: body },
            429 => Self::RateLimited { retry_after },
            529 => Self::Overloaded { retry_after },
            status => Self::Unexpected { status, body },
        }
    }

    /// Whether sending the request again could succeed: rate limits, overloads, and transport
    /// failures are worth a retry; everything else is not.
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            Self::RateLimited { .. } | Self::Overloaded { .. } | Self::Transport(_)
        )
    }

    /// The delay the API asked for, when it sent one.
    pub fn retry_after(&self) -> Option<Duration> {
        match self {
            Self::RateLimited { retry_after } | Self::Overloaded { retry_after } => *retry_after,
            _ => None,
        }
    }
}
