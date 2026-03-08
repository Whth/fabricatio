use crate::model::{CompletionModel, EmbeddingModel};
use crate::models::openai::OpenaiModel;
use crate::provider::{ProvideCompletionModel, ProvideEmbeddingModel, Provider};
use crate::Result;
use http::header::AUTHORIZATION;
use http::{HeaderMap, HeaderValue};
use reqwest::Url;
use secrecy::{ExposeSecret, SecretString};
use std::sync::Arc;

pub struct OpenaiCompatible {
    endpoint: Url,
    api_key: SecretString,
}


impl Default for OpenaiCompatible {
    fn default() -> Self {
        Self {
            endpoint: Url::parse("https://api.openai.com/v1").unwrap(),
            api_key: Default::default(),
        }
    }
}


impl Provider for OpenaiCompatible {
    fn provider_name(&self) -> &'static str {
        "openai"
    }

    fn endpoint(&self) -> Url {
        self.endpoint.clone()
    }

    fn headers(&self) -> Result<HeaderMap> {
        build_headers(&self.api_key)
    }
}

impl ProvideCompletionModel for OpenaiCompatible {
    fn create_completion_model(self: Arc<Self>, model_name: String) -> Result<Box<dyn CompletionModel>> {
        Ok(Box::new(OpenaiModel::new(model_name, self)))
    }
}


impl ProvideEmbeddingModel for OpenaiCompatible {
    fn create_embedding_model(self: Arc<Self>, model_name: String) -> Result<Box<dyn EmbeddingModel>> {
        Ok(Box::new(OpenaiModel::new(model_name, self)))
    }
}


pub(crate) fn build_headers(key: &SecretString) -> Result<HeaderMap> {
    let mut h = HeaderMap::new();


    let mut auth_header = HeaderValue::from_str(format!("Bearer {}", key.expose_secret()).as_str())?;

    auth_header.set_sensitive(true);

    h.insert(AUTHORIZATION,
             auth_header);
    Ok(h)
}

