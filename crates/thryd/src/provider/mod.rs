pub mod openai;

use crate::connections::{ClientEntry, CONNECTIONS_POOL};
use crate::{Result, ThrydError};
use async_trait::async_trait;
use reqwest::header::HeaderMap;
use reqwest::Client;
use std::sync::Arc;
use url::Url;

#[async_trait]
pub trait Provider: Send + Sync {
    fn name(&self) -> &'static str;

    /// Returns a type-erased reference to the underlying client.
    fn endpoint(&self) -> Url;


    fn client(&self) -> Result<ClientEntry> {
        CONNECTIONS_POOL.try_get_with(
            self.endpoint(),
            || Ok(Arc::new(Client::builder().default_headers(self.headers()?).build()?)),
        )
            .map_err(
                |e: Arc<ThrydError>| {
                    ThrydError::ClientError { name: self.name().to_string(), msg: e.to_string() }
                }
            )
    }

    fn headers(&self) -> Result<HeaderMap>;
}



