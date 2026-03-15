use crate::provider::Provider;
use crate::utils::build_headers;
use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
pub struct DummyProvider {
    endpoint: Url,
    api_key: SecretString,
    name: String,
}


impl Default for DummyProvider {
    fn default() -> Self {
        Self {
            endpoint: Url::parse("https://api.openai.com/v1").unwrap(),
            api_key: Default::default(),
            name: "dummy".to_string(),
        }
    }
}


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
}