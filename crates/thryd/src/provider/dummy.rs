use crate::provider::Provider;
use crate::utils::build_headers;
use crate::{CompletionModel, DummyModel, EmbeddingModel, ModelName, RerankerModel};
use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
use std::sync::Arc;

/// A dummy provider for testing and development.
///
/// This provider does not make real HTTP calls to any LLM API.
/// It is useful for:
/// - Unit testing without network access
/// - Development when API quota is limited
/// - Mocking provider behavior in integration tests
///
/// # Note
///
/// The dummy provider will return dummy responses through the
/// [`DummyModel`] implementation. It does not simulate realistic
/// API responses.
///
/// # Example
///
/// ```rust,ignore
/// use thryd::provider::DummyProvider;
///
/// let provider = DummyProvider::default();
/// ```
pub struct DummyProvider {
    endpoint: Url,
    api_key: SecretString,
    name: String,
}

/// Default implementation for DummyProvider.
///
/// Creates a dummy provider with:
/// - Endpoint: `https://api.openai.com/v1` (placeholder, not used)
/// - Name: `"dummy"`
/// - Empty API key (not used)
///
/// # Example
///
/// ```rust,ignore
/// let provider = DummyProvider::default();
/// ```
impl Default for DummyProvider {
    fn default() -> Self {
        Self {
            endpoint: Url::parse("https://api.openai.com/v1").unwrap(),
            api_key: Default::default(),
            name: "dummy".to_string(),
        }
    }
}

/// Implements the [`Provider`] trait for DummyProvider.
///
/// This implementation does not make real HTTP calls. All model
/// operations return dummy responses via [`DummyModel`].
impl Provider for DummyProvider {
    fn provider_name(&self) -> &str {
        self.name.as_str()
    }

    fn endpoint(&self) -> Url {
        self.endpoint.clone()
    }

    fn headers(&self) -> crate::Result<HeaderMap> {
        build_headers(&self.api_key)
    }

    fn create_completion_model(
        self: Arc<Self>,
        model_name: String,
    ) -> crate::Result<Box<dyn CompletionModel>> {
        Ok(Box::new(DummyModel::new(model_name, self)))
    }

    fn create_embedding_model(
        self: Arc<Self>,
        model_name: String,
    ) -> crate::Result<Box<dyn EmbeddingModel>> {
        Ok(Box::new(DummyModel::new(model_name, self)))
    }

    fn create_reranker_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> crate::Result<Box<dyn RerankerModel>> {
        Ok(Box::new(DummyModel::new(model_name, self)))
    }
}
