use crate::Result;
use crate::model::{CompletionModel, EmbeddingModel};
use crate::models::openai::OpenaiModel;
use crate::provider::{ProvideCompletionModel, ProvideEmbeddingModel, Provider};
use crate::utils::build_headers;
use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
use std::sync::Arc;

pub struct OpenaiCompatible {
    endpoint: Url,
    api_key: SecretString,
    name: String,
}

impl Default for OpenaiCompatible {
    fn default() -> Self {
        Self {
            endpoint: Url::parse("https://api.openai.com/v1").unwrap(),
            api_key: Default::default(),
            name: "openai".to_string(),
        }
    }
}

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
}

impl ProvideCompletionModel for OpenaiCompatible {
    fn create_completion_model(
        self: Arc<Self>,
        model_name: String,
    ) -> Result<Box<dyn CompletionModel>> {
        Ok(Box::new(OpenaiModel::new(model_name, self)))
    }
}

impl ProvideEmbeddingModel for OpenaiCompatible {
    fn create_embedding_model(
        self: Arc<Self>,
        model_name: String,
    ) -> Result<Box<dyn EmbeddingModel>> {
        Ok(Box::new(OpenaiModel::new(model_name, self)))
    }
}
