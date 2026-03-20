pub mod dummy;
pub mod openai;

pub use dummy::*;
pub use openai::*;

use crate::connections::{CONNECTIONS_POOL, ClientEntry};
use crate::model::{CompletionModel, EmbeddingModel};
use crate::{Result, ThrydError};
use async_trait::async_trait;
use reqwest::header::HeaderMap;
use reqwest::{Client, Response};
use serde_json::Value;
use std::sync::Arc;
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
}

pub trait ProvideCompletionModel: Provider {
    fn create_completion_model(
        self: Arc<Self>,
        model_name: String,
    ) -> Result<Box<dyn CompletionModel>>;
}

pub trait ProvideEmbeddingModel: Provider {
    fn create_embedding_model(
        self: Arc<Self>,
        model_name: String,
    ) -> Result<Box<dyn EmbeddingModel>>;
}
