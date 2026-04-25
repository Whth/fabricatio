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

#[async_trait]
pub trait Provider: Send + Sync {
    fn provider_name(&self) -> &str;

    /// Returns a type-erased reference to the underlying client.
    fn endpoint(&self) -> Url;

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

    async fn get(&self, path: &str, data: &Value) -> Result<Response> {
        self.client()?
            .get(self.endpoint().join(path)?)
            .json(data)
            .send()
            .await
            .map_err(ThrydError::from)
    }

    async fn post(&self, path: &str, data: &Value) -> Result<Response> {
        self.client()?
            .post(self.endpoint().join(path)?)
            .json(data)
            .send()
            .await
            .map_err(ThrydError::from)
    }

    fn headers(&self) -> Result<HeaderMap>;

    fn create_completion_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> Result<Box<dyn CompletionModel>> {
        Err(ModelNotSupported {
            model: model_name,
            provider: self.provider_name().to_string(),
        })
    }

    fn create_embedding_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> Result<Box<dyn EmbeddingModel>> {
        Err(ModelNotSupported {
            model: model_name,
            provider: self.provider_name().to_string(),
        })
    }

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

#[derive(EnumString, Debug, Deserialize, Serialize)]
#[cfg_attr(feature = "pyo3", pyo3::pyclass(from_py_object), derive(Clone))]
#[cfg_attr(feature = "pystub", pyo3_stub_gen::derive::gen_stub_pyclass_enum)]
pub enum ProviderType {
    OpenAI,
    OpenAICompatible,
    Dummy,
}

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
