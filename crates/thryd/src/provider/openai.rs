use crate::provider::Provider;
use http::header::AUTHORIZATION;
use http::HeaderMap;
use reqwest::Url;
use secrecy::{ExposeSecret, SecretString};

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
    fn name(&self) -> &'static str {
        "openai"
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