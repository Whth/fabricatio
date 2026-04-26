pub mod dummy;
pub mod openai;

pub use dummy::*;
pub use openai::*;

use crate::ThrydError::ModelNotSupported;
use crate::connections::{CONNECTIONS_POOL, ClientEntry};
use crate::model::{CompletionModel, EmbeddingModel};
use crate::{ModelName, ProviderName, RerankerModel, Result, ThrydError};
use async_trait::async_trait;
use reqwest::header::HeaderMap;
use reqwest::{Client, Response};
use secrecy::SecretString;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::Arc;
use strum_macros::EnumString;
use url::Url;

/// Trait for LLM API providers.
///
/// Implement this trait to add support for new LLM providers.
/// Providers handle HTTP communication with LLM services and expose
/// model creation through a unified interface.
///
/// # Example
///
/// ```rust,ignore
/// use async_trait::async_trait;
/// use thryd::provider::Provider;
/// use http::HeaderMap;
/// use reqwest::Url;
/// use secrecy::SecretString;
///
/// struct MyProvider {
///     endpoint: Url,
///     api_key: SecretString,
///     name: String,
/// }
///
/// #[async_trait]
/// impl Provider for MyProvider {
///     fn provider_name(&self) -> &str {
///         &self.name
///     }
///
///     fn endpoint(&self) -> Url {
///         self.endpoint.clone()
///     }
///
///     fn headers(&self) -> Result<HeaderMap> {
///         let mut headers = HeaderMap::new();
///         headers.insert("Authorization", format!("Bearer {}", self.api_key).parse()?);
///         Ok(headers)
///     }
/// }
/// ```
#[async_trait]
pub trait Provider: Send + Sync {
    /// Returns the provider's identifier name.
    ///
    /// This name is used for error reporting and logging.
    fn provider_name(&self) -> &str;

    /// Returns the base URL endpoint for the provider's API.
    ///
    /// This URL is combined with path parameters to form complete API requests.
    /// All HTTP requests made by the provider will be relative to this endpoint.
    fn endpoint(&self) -> Url;

    /// Returns a pooled HTTP client configured with the provider's headers.
    ///
    /// The client is cached per-endpoint using a connection pool.
    /// Returns an error if header construction fails or client creation fails.
    fn client(&self) -> Result<ClientEntry> {
        CONNECTIONS_POOL
            .try_get_with(self.endpoint(), || {
                Ok(Arc::new(
                    Client::builder().default_headers(self.headers()?).build()?,
                ))
            })
            .map_err(|e: Arc<ThrydError>| ThrydError::ClientError {
                name: self.provider_name().to_string(),
                msg: e.to_string(),
            })
    }

    /// Performs an HTTP GET request to the specified path with JSON body.
    ///
    /// # Arguments
    /// * `path` - The API endpoint path (relative to the base endpoint)
    /// * `data` - JSON body to send with the request
    ///
    /// # Returns
    /// The HTTP response from the provider.
    async fn get(&self, path: &str, data: &Value) -> Result<Response> {
        self.client()?
            .get(self.endpoint().join(path)?)
            .json(data)
            .send()
            .await
            .map_err(ThrydError::from)
    }

    /// Performs an HTTP POST request to the specified path with JSON body.
    ///
    /// # Arguments
    /// * `path` - The API endpoint path (relative to the base endpoint)
    /// * `data` - JSON body to send with the request
    ///
    /// # Returns
    /// The HTTP response from the provider.
    async fn post(&self, path: &str, data: &Value) -> Result<Response> {
        self.client()?
            .post(self.endpoint().join(path)?)
            .json(data)
            .send()
            .await
            .map_err(ThrydError::from)
    }

    /// Returns the HTTP headers required for requests to this provider.
    ///
    /// Typically includes authentication headers like `Authorization: Bearer <token>`.
    /// Returns an error if header construction fails.
    fn headers(&self) -> Result<HeaderMap>;

    /// Creates a completion model for text generation tasks.
    ///
    /// # Arguments
    /// * `model_name` - The name/identifier of the model to create
    ///
    /// # Returns
    /// A boxed completion model, or an error if the model is not supported.
    ///
    /// # Default Implementation
    ///
    /// The default implementation returns `ModelNotSupported` error.
    /// Providers that support completions should override this method.
    fn create_completion_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> Result<Box<dyn CompletionModel>> {
        Err(ModelNotSupported {
            model: model_name,
            provider: self.provider_name().to_string(),
        })
    }

    /// Creates an embedding model for text vectorization tasks.
    ///
    /// # Arguments
    /// * `model_name` - The name/identifier of the model to create
    ///
    /// # Returns
    /// A boxed embedding model, or an error if the model is not supported.
    ///
    /// # Default Implementation
    ///
    /// The default implementation returns `ModelNotSupported` error.
    /// Providers that support embeddings should override this method.
    fn create_embedding_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> Result<Box<dyn EmbeddingModel>> {
        Err(ModelNotSupported {
            model: model_name,
            provider: self.provider_name().to_string(),
        })
    }

    /// Creates a reranker model for document reordering tasks.
    ///
    /// # Arguments
    /// * `model_name` - The name/identifier of the model to create
    ///
    /// # Returns
    /// A boxed reranker model, or an error if the model is not supported.
    ///
    /// # Default Implementation
    ///
    /// The default implementation returns `ModelNotSupported` error.
    /// Providers that support reranking should override this method.
    fn create_reranker_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> Result<Box<dyn RerankerModel>> {
        Err(ModelNotSupported {
            model: model_name,
            provider: self.provider_name().to_string(),
        })
    }
}

/// Enum representing supported LLM provider types.
///
/// Use this enum to specify which type of provider to create
/// when calling [`create_provider`].
///
/// # Variants
///
/// * `OpenAI` - Official OpenAI API provider. Requires an API key,
///   falls back to `OPENAI_API_KEY` environment variable.
/// * `OpenAICompatible` - Any OpenAI API-compatible provider (Azure OpenAI,
///   LocalAI, custom endpoints). Requires name, API key, and endpoint URL.
/// * `Dummy` - A provider that doesn't make real HTTP calls. Useful for
///   testing and development.
#[derive(EnumString, Debug, Deserialize, Serialize)]
#[cfg_attr(feature = "pyo3", pyo3::pyclass(from_py_object), derive(Clone))]
#[cfg_attr(feature = "pystub", pyo3_stub_gen::derive::gen_stub_pyclass_enum)]
pub enum ProviderType {
    /// Official OpenAI API provider.
    OpenAI,
    /// OpenAI API-compatible provider (Azure, LocalAI, custom endpoints).
    OpenAICompatible,
    /// Dummy provider for testing (does not make real HTTP calls).
    Dummy,
}

/// Helper function that validates all required provider configuration parameters.
///
/// Returns an error if any of the parameters are missing.
///
/// # Arguments
///
/// * `name` - The provider's name identifier
/// * `api_key` - The API key for authentication
/// * `endpoint` - The base URL endpoint for the API
///
/// # Returns
///
/// A tuple of `(name, api_key, parsed_endpoint_url)` on success.
///
/// # Errors
///
/// Returns `ProviderCreate` error with a descriptive message if any
/// parameter is `None`.
fn need_all(
    name: Option<ProviderName>,
    api_key: Option<SecretString>,
    endpoint: Option<String>,
) -> Result<(String, SecretString, Url)> {
    Ok((
        name.ok_or_else(|| ThrydError::ProviderCreate("Name not provided!".to_string()))?,
        SecretString::from(
            api_key
                .ok_or_else(|| ThrydError::ProviderCreate("API key not provided!".to_string()))?,
        ),
        endpoint
            .ok_or_else(|| ThrydError::ProviderCreate("Endpoint not provided!".to_string()))?
            .parse()?,
    ))
}

/// Factory function to create a provider instance from configuration.
///
/// # Arguments
///
/// * `provider_type` - The type of provider to create
/// * `name` - Provider name (required for `OpenAICompatible`, optional for others)
/// * `api_key` - API key for authentication (required for `OpenAICompatible` and `OpenAI`)
/// * `endpoint` - Base URL endpoint (required for `OpenAICompatible`, unused for others)
///
/// # Returns
///
/// A thread-safe, cloned `Arc` reference to the created provider.
///
/// # Provider-Specific Behavior
///
/// * `OpenAI` - Creates an OpenAI provider. The `api_key` parameter is required,
///   but if not provided, will attempt to read from `OPENAI_API_KEY` environment variable.
///   The `name` and `endpoint` parameters are ignored.
///
/// * `OpenAICompatible` - Creates a custom OpenAI-compatible provider.
///   All parameters are required.
///
/// * `Dummy` - Creates a dummy provider that doesn't make real HTTP calls.
///   All parameters are ignored.
///
/// # Example
///
/// ```rust,ignore
/// use thryd::provider::{create_provider, ProviderType};
/// use secrecy::SecretString;
///
/// // Create an OpenAI-compatible provider
/// let provider = create_provider(
///     ProviderType::OpenAICompatible,
///     Some("my-provider".to_string()),
///     Some(SecretString::from("sk-...")),
///     Some("https://api.example.com/v1".to_string()),
/// ).unwrap();
///
/// // Create a dummy provider for testing
/// let dummy = create_provider(
///     ProviderType::Dummy,
///     None,
///     None,
///     None,
/// ).unwrap();
/// ```
pub fn create_provider(
    provider_type: ProviderType,
    name: Option<ProviderName>,
    api_key: Option<SecretString>,
    endpoint: Option<String>,
) -> Result<Arc<dyn Provider>> {
    match provider_type {
        ProviderType::OpenAI => Ok(Arc::new(
            api_key
                .ok_or_else(|| {
                    ThrydError::ProviderCreate("OpenAI API key not provided!".to_string())
                })
                .map(OpenaiCompatible::openai)
                .or_else(|e| OpenaiCompatible::openai_from_env().ok_or(e))?,
        )),
        ProviderType::OpenAICompatible => {
            let (name, api_key, endpoint) = need_all(name, api_key, endpoint)?;

            Ok(Arc::new(OpenaiCompatible::new(name, api_key, endpoint)))
        }
        ProviderType::Dummy => Ok(Arc::new(DummyProvider::default())),
    }
}
