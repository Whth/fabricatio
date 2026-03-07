use crate::provider::Provider;
use http::header::AUTHORIZATION;
use http::HeaderMap;
use reqwest::Url;
use secrecy::{ExposeSecret, SecretString};

pub struct DummyProvider {
    endpoint: Url,
    api_key: SecretString,
}


impl Default for DummyProvider {
    fn default() -> Self {
        Self {
            endpoint: Url::parse("https://api.openai.com/v1").unwrap(),
            api_key: Default::default(),
        }
    }
}


impl Provider for DummyProvider {
    fn provider_name(&self) -> &'static str {
        "dummy"
    }

    fn endpoint(&self) -> Url {
        self.endpoint.clone()
    }

    fn headers(&self) -> crate::Result<HeaderMap> {
        let mut h = HeaderMap::new();

        h.insert(AUTHORIZATION,
                 format!("Bearer {}", self.api_key.expose_secret()).parse()?);
        Ok(h)
    }
}