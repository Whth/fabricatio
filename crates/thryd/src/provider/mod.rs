pub mod openai;
pub mod dummy;

use crate::connections::{ClientEntry, CONNECTIONS_POOL};
use crate::{Result, ThrydError};
use async_trait::async_trait;
use reqwest::header::HeaderMap;
use reqwest::{Client, Response};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::Arc;
use url::Url;

#[async_trait]
pub trait Provider: Send + Sync {
    fn provider_name(&self) -> &'static str;

    /// Returns a type-erased reference to the underlying client.
    fn endpoint(&self) -> Url;


    fn client(&self) -> Result<ClientEntry> {
        CONNECTIONS_POOL.try_get_with(
            self.endpoint(),
            || Ok(Arc::new(Client::builder().default_headers(self.headers()?).build()?)),
        )
            .map_err(
                |e: Arc<ThrydError>| {
                    ThrydError::ClientError { name: self.provider_name().to_string(), msg: e.to_string() }
                }
            )
    }


    async fn get(&self, path: &str, data: &Value) -> Result<Response> {
        self.client()?.get(self.endpoint().join(path)?)
            .json(data)
            .send().await
            .map_err(ThrydError::from)
    }

    async fn post(&self, path: &str, data: &Value) -> Result<Response> {
        self.client()?.post(self.endpoint().join(path)?)
            .json(data)
            .send().await
            .map_err(ThrydError::from)
    }

    fn headers(&self) -> Result<HeaderMap>;
}



