use crate::model::{CompletionModel, EmbeddingModel};
use crate::models::openai::OpenaiModel;
use crate::provider::{ProvideCompletionModel, ProvideEmbeddingModel, Provider};
use crate::utils::build_headers;
use crate::Result;
use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
use std::env::var;
use std::sync::Arc;

pub struct OpenaiCompatible {
    endpoint: Url,
    api_key: SecretString,
    name: String,
}


impl OpenaiCompatible {
    pub fn new(name: String, api_key: SecretString, endpoint: Url) -> Self {
        Self {
            endpoint,
            api_key,
            name,
        }
    }


    pub fn openai(api_key: SecretString) -> Self {
        Self {
            api_key,
            ..Self::default()
        }
    }

    pub fn openai_from_env() -> Option<Self> {
        var("OPENAI_API_KEY").ok()
            .map(
                |k|
                    Self::openai(SecretString::from(k))
            )
    }
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
