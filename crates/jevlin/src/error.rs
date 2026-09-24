//! The error taxonomy.

#[cfg(feature = "client")]
use std::time::Duration;

#[cfg(feature = "client")]
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
///
/// Building a request and reading a response need no HTTP stack: they fail with
/// [`Invalid`](Self::Invalid), [`MissingAnswer`](Self::MissingAnswer) or [`Decode`](Self::Decode).
/// The variants describing what the client ran into are compiled in with the `client` feature,
/// which is on by default.
#[derive(Debug, Error)]
pub enum Error {
    /// The request breaks the API's own constraints, so it was not sent.
    #[error(transparent)]
    Invalid(#[from] InvalidRequest),

    /// No API key was available.
    #[cfg(feature = "client")]
    #[error("no API key: pass one to the client, or set the JEVLIN_API_KEY environment variable")]
    MissingApiKey,

    /// The base URL is not a URL.
    #[cfg(feature = "client")]
    #[error("invalid base URL `{url}`: {reason}")]
    InvalidBaseUrl {
        /// The URL as given.
        url: String,
        /// Why it could not be parsed.
        reason: String,
    },

    /// `401 Unauthorized`: the API key is missing or invalid.
    #[cfg(feature = "client")]
    #[error("authentication failed: check the API key (401)")]
    Unauthorized,

    /// `422 Unprocessable Entity`: the API rejected the request body.
    #[cfg(feature = "client")]
    #[error("the API rejected the request body (422): {detail}")]
    Unprocessable {
        /// The body the API returned, which names the offending field.
        detail: String,
    },

    /// `429 Too Many Requests`: the rate limit is exhausted.
    #[cfg(feature = "client")]
    #[error("rate limited by the API (429)")]
    RateLimited {
        /// The delay the API asked for, when it sent one.
        retry_after: Option<Duration>,
    },

    /// `529 Overloaded`: the API is temporarily overloaded.
    #[cfg(feature = "client")]
    #[error("the API is overloaded (529)")]
    Overloaded {
        /// The delay the API asked for, when it sent one.
        retry_after: Option<Duration>,
    },

    /// Any other status.
    #[cfg(feature = "client")]
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
    #[cfg(feature = "client")]
    #[error(transparent)]
    Transport(#[from] reqwest::Error),

    /// A response body did not match the shape the API documents.
    #[error(transparent)]
    Decode(#[from] serde_json::Error),
}

#[cfg(feature = "client")]
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
