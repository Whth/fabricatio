//! OpenAI Responses API provider.
//!
//! Like [`crate::provider::OpenaiCompatible`], but completion models talk to
//! the OpenAI Responses API (`POST /v1/responses`) instead of chat completions.
//!
//! # Example
//!
//! ```rust,ignore
//! use thryd::provider::OpenaiResponses;
//! use secrecy::SecretString;
//! use reqwest::Url;
//!
//! let provider = OpenaiResponses::new(
//!     "openai".to_string(),
//!     SecretString::from("sk-..."),
//!     Url::parse("https://api.openai.com/v1").unwrap(),
//! );
//! ```

use crate::Result;
use crate::model::CompletionModel;
use crate::models::responses::OpenaiResponsesModel;
use crate::provider::Provider;
use crate::utils::build_headers;
use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
use std::sync::Arc;

/// An OpenAI Responses API provider.
///
/// Completion models issued by this provider send requests to the
/// `responses` endpoint. Embedding and reranker models are not supported
/// (the Responses API has no such endpoints).
pub struct OpenaiResponses {
    endpoint: Url,
    api_key: SecretString,
    name: String,
}

impl OpenaiResponses {
    /// Creates a new OpenAI Responses API provider with a custom endpoint.
    ///
    /// # Arguments
    ///
    /// * `name` - A human-readable name for this provider (used in error messages)
    /// * `api_key` - The API key for authentication
    /// * `endpoint` - The base URL of the API (e.g., `https://api.openai.com/v1`)
    pub fn new(name: String, api_key: SecretString, endpoint: Url) -> Self {
        Self {
            endpoint,
            api_key,
            name,
        }
    }
}

/// Implements the [`Provider`] trait for the OpenAI Responses API.
///
/// This implementation supports:
/// - Completion models (Responses API)
///
/// # Headers
///
/// Sets the `Authorization` header with `Bearer <api_key>` and
/// `Content-Type: application/json`.
impl Provider for OpenaiResponses {
    fn provider_name(&self) -> &str {
        self.name.as_str()
    }

    fn endpoint(&self) -> Url {
        self.endpoint.clone()
    }

    fn headers(&self) -> Result<HeaderMap> {
        build_headers(&self.api_key)
    }

    fn create_completion_model(
        self: Arc<Self>,
        model_name: String,
    ) -> Result<Box<dyn CompletionModel>> {
        Ok(Box::new(OpenaiResponsesModel::new(model_name, self)))
    }
}
