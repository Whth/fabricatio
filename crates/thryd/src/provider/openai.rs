use crate::Result;
use crate::model::{CompletionModel, EmbeddingModel};
use crate::models::openai::OpenaiModel;
use crate::provider::Provider;
use crate::utils::build_headers;
use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
use std::env::var;
use std::sync::Arc;

/// An OpenAI API-compatible provider.
///
/// This provider can work with:
/// - Official OpenAI API
/// - Azure OpenAI
/// - LocalAI
/// - Any other OpenAI-compatible API endpoint
///
/// # Example
///
/// ```rust,ignore
/// use thryd::provider::OpenaiCompatible;
/// use secrecy::SecretString;
/// use reqwest::Url;
///
/// // For official OpenAI
/// let openai = OpenaiCompatible::openai(SecretString::from("sk-..."));
///
/// // For custom endpoint
/// let custom = OpenaiCompatible::new(
///     "my-model".to_string(),
///     SecretString::from("sk-..."),
///     Url::parse("https://api.example.com/v1").unwrap(),
/// );
/// ```
pub struct OpenaiCompatible {
    endpoint: Url,
    api_key: SecretString,
    name: String,
}

impl OpenaiCompatible {
    /// Creates a new OpenAI-compatible provider with a custom endpoint.
    ///
    /// # Arguments
    ///
    /// * `name` - A human-readable name for this provider (used in error messages)
    /// * `api_key` - The API key for authentication
    /// * `endpoint` - The base URL of the API (e.g., `https://api.example.com/v1`)
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// use thryd::provider::OpenaiCompatible;
    /// use secrecy::SecretString;
    /// use reqwest::Url;
    ///
    /// let provider = OpenaiCompatible::new(
    ///     "azure-openai".to_string(),
    ///     SecretString::from("azure-api-key"),
    ///     Url::parse("https://my-resource.openai.azure.com/v1").unwrap(),
    /// );
    /// ```
    pub fn new(name: String, api_key: SecretString, endpoint: Url) -> Self {
        Self {
            endpoint,
            api_key,
            name,
        }
    }

    /// Creates a provider for the official OpenAI API.
    ///
    /// Uses `https://api.openai.com/v1` as the endpoint.
    ///
    /// # Arguments
    ///
    /// * `api_key` - Your OpenAI API key
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// use thryd::provider::OpenaiCompatible;
    /// use secrecy::SecretString;
    ///
    /// let openai = OpenaiCompatible::openai(SecretString::from("sk-..."));
    /// ```
    pub fn openai(api_key: SecretString) -> Self {
        Self {
            api_key,
            ..Self::default()
        }
    }

    /// Creates an official OpenAI provider using the `OPENAI_API_KEY` environment variable.
    ///
    /// # Returns
    ///
    /// `Some(OpenaiCompatible)` if `OPENAI_API_KEY` is set, `None` otherwise.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Set environment variable before running
    /// std::env::set_var("OPENAI_API_KEY", "sk-...");
    ///
    /// let openai = OpenaiCompatible::openai_from_env();
    /// ```
    pub fn openai_from_env() -> Option<Self> {
        var("OPENAI_API_KEY")
            .ok()
            .map(|k| Self::openai(SecretString::from(k)))
    }
}

/// Default implementation for OpenAI-compatible provider.
///
/// Sets up a provider with:
/// - Endpoint: `https://api.openai.com/v1`
/// - Name: `"openai"`
/// - Empty API key (must be set before use)
///
/// # Example
///
/// ```rust,ignore
/// let provider = OpenaiCompatible::default();
/// // API key is empty - you'll need to set it via one of the constructors
/// ```
impl Default for OpenaiCompatible {
    fn default() -> Self {
        Self {
            endpoint: Url::parse("https://api.openai.com/v1").unwrap(),
            api_key: Default::default(),
            name: "openai".to_string(),
        }
    }
}

/// Implements the [`Provider`] trait for OpenAI-compatible APIs.
///
/// This implementation supports:
/// - Completion models (chat completions)
/// - Embedding models
///
/// # Headers
///
/// Sets the `Authorization` header with `Bearer <api_key>` and
/// `Content-Type: application/json`.
impl Provider for OpenaiCompatible {
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
        Ok(Box::new(OpenaiModel::new(model_name, self)))
    }

    fn create_embedding_model(
        self: Arc<Self>,
        model_name: String,
    ) -> Result<Box<dyn EmbeddingModel>> {
        Ok(Box::new(OpenaiModel::new(model_name, self)))
    }
}
