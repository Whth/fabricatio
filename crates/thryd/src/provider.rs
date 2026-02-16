use crate::error::{Result, ThrydError};
use crate::tracker::UsageTracker;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fmt::Debug;
use std::sync::Arc;
use tokio::sync::RwLock;

/// A trait for LLM model interactions
#[async_trait]
pub trait Model: Send + Sync {
    /// Returns the model name identifier
    fn name(&self) -> &str;

    /// Returns the provider name
    fn provider(&self) -> &str;

    /// Make a chat completion request
    async fn completion(&self, request: Value) -> Result<Value>;

    /// Get the underlying client
    fn client(&self) -> &dyn std::any::Any;
}

/// Represents a deployed LLM model configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Deployment {
    pub name: String,
    pub provider: String,
    pub model: String,
    pub api_base: Option<String>,
    pub max_tokens: Option<u32>,
    pub temperature: Option<f32>,
}

impl Deployment {
    pub fn new(name: impl Into<String>, provider: impl Into<String>, model: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            provider: provider.into(),
            model: model.into(),
            api_base: None,
            max_tokens: None,
            temperature: None,
        }
    }

    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = Some(api_base.into());
        self
    }

    pub fn with_max_tokens(mut self, max_tokens: u32) -> Self {
        self.max_tokens = Some(max_tokens);
        self
    }

    pub fn with_temperature(mut self, temperature: f32) -> Self {
        self.temperature = Some(temperature);
        self
    }
}

/// Information about a provider's rate limits
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitInfo {
    pub requests_per_minute: Option<u32>,
    pub tokens_per_minute: Option<u32>,
}

impl Default for RateLimitInfo {
    fn default() -> Self {
        Self {
            requests_per_minute: Some(60),
            tokens_per_minute: Some(90000),
        }
    }
}

/// Represents an LLM provider with its configuration and client
pub struct LlmProvider {
    name: String,
    deployment: Deployment,
    http_client: reqwest::Client,
    rate_limit: RateLimitInfo,
    usage_tracker: Arc<RwLock<UsageTracker>>,
}

impl Debug for LlmProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("LlmProvider")
            .field("name", &self.name)
            .field("deployment", &self.deployment)
            .finish()
    }
}

impl LlmProvider {
    /// Create a new provider from deployment config
    pub fn new(deployment: Deployment, api_key: secrecy::SecretString) -> Result<Self> {
        Self::with_api_base(deployment, api_key, None)
    }

    /// Create a new provider with custom API base URL
    pub fn with_api_base(
        deployment: Deployment,
        api_key: secrecy::SecretString,
        api_base: Option<String>,
    ) -> Result<Self> {
        let _ = api_key; // Suppress unused warning
        let _base_url = api_base
            .or_else(|| deployment.api_base.clone())
            .unwrap_or_else(|| "https://api.openai.com/v1".to_string());

        let client = reqwest::Client::new();

        let rate_limit = RateLimitInfo::default();

        // Create tracker with rate limits
        let usage_tracker = Arc::new(RwLock::new(UsageTracker::new(
            rate_limit.tokens_per_minute.unwrap_or(90000),
            rate_limit.requests_per_minute.unwrap_or(60),
            60_000, // 1 minute window
        )));

        Ok(Self {
            name: deployment.name.clone(),
            deployment,
            http_client: client,
            rate_limit,
            usage_tracker,
        })
    }

    /// Get provider name
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Get deployment info
    pub fn deployment(&self) -> &Deployment {
        &self.deployment
    }

    /// Get rate limit info
    pub fn rate_limit(&self) -> &RateLimitInfo {
        &self.rate_limit
    }

    /// Check if provider can handle a request now
    pub async fn can_handle(&self, estimated_tokens: u32) -> bool {
        let tracker = self.usage_tracker.read().await;
        tracker.can_make_request(estimated_tokens)
    }

    /// Get estimated wait time in milliseconds
    pub async fn estimated_wait_time(&self, estimated_tokens: u32) -> u64 {
        let tracker = self.usage_tracker.read().await;
        tracker.estimated_waiting_time_for_tokens(estimated_tokens)
    }

    /// Record a request's token usage
    pub async fn record_usage(&self, input_tokens: u32, output_tokens: u32) {
        let mut tracker = self.usage_tracker.write().await;
        tracker.add_request(input_tokens, output_tokens);
    }

    /// Get current usage stats
    pub async fn usage_stats(&self) -> UsageStats {
        let tracker = self.usage_tracker.read().await;
        UsageStats {
            requests_in_window: tracker.request_usage(),
            tokens_in_window: tracker.token_usage() as u32,
            remaining_requests: tracker.remaining_requests().unwrap_or(0),
            remaining_tokens: tracker.remaining_tokens().unwrap_or(0) as u32,
        }
    }

    /// Send a chat completion request using the OpenAI API directly via HTTP
    pub async fn chat(&self, messages: Vec<Value>) -> Result<Value> {
        let request_body = serde_json::json!({
            "model": self.deployment.model,
            "messages": messages,
        });

        let base_url = self.deployment.api_base.clone()
            .unwrap_or_else(|| "https://api.openai.com/v1".to_string());
        
        let url = format!("{}/chat/completions", base_url.trim_end_matches('/'));
        
        let response = self.http_client
            .post(&url)
            .header("Content-Type", "application/json")
            .json(&request_body)
            .send()
            .await?;

        let response_json: Value = response.json().await?;
        Ok(response_json)
    }

    /// Send a raw chat completion request from Value
    pub async fn completion(&self, request: Value) -> Result<Value> {
        let base_url = self.deployment.api_base.clone()
            .unwrap_or_else(|| "https://api.openai.com/v1".to_string());
        
        let url = format!("{}/chat/completions", base_url.trim_end_matches('/'));
        
        let response = self.http_client
            .post(&url)
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await?;

        let response_json: Value = response.json().await?;
        Ok(response_json)
    }
}

#[async_trait]
impl Model for LlmProvider {
    fn name(&self) -> &str {
        &self.name
    }

    fn provider(&self) -> &str {
        &self.deployment.provider
    }

    async fn completion(&self, request: Value) -> Result<Value> {
        self.completion(request).await
    }

    fn client(&self) -> &dyn std::any::Any {
        self
    }
}

/// Current usage statistics for a provider
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageStats {
    pub requests_in_window: u32,
    pub tokens_in_window: u32,
    pub remaining_requests: u32,
    pub remaining_tokens: u32,
}

/// Builder for creating LlmProvider instances
pub struct ProviderBuilder {
    deployment: Deployment,
    api_key: Option<secrecy::SecretString>,
    api_base: Option<String>,
    rate_limit: Option<RateLimitInfo>,
}

impl ProviderBuilder {
    pub fn new(name: impl Into<String>, provider: impl Into<String>, model: impl Into<String>) -> Self {
        Self {
            deployment: Deployment::new(name, provider, model),
            api_key: None,
            api_base: None,
            rate_limit: None,
        }
    }

    pub fn with_api_key(mut self, api_key: impl Into<String>) -> Self {
        let key = api_key.into().into_boxed_str();
        self.api_key = Some(secrecy::SecretString::new(key));
        self
    }

    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = Some(api_base.into());
        self
    }

    pub fn with_rate_limit(mut self, rate_limit: RateLimitInfo) -> Self {
        self.rate_limit = Some(rate_limit);
        self
    }

    pub fn build(self) -> Result<LlmProvider> {
        let _api_key = self.api_key.ok_or_else(|| {
            ThrydError::InvalidRequest("API key is required".to_string())
        })?;

        let mut provider = LlmProvider::with_api_base(self.deployment, _api_key, self.api_base)?;

        if let Some(rl) = self.rate_limit {
            provider.rate_limit = rl;
        }

        Ok(provider)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deployment_new() {
        let deployment = Deployment::new("test", "openai", "gpt-4");
        assert_eq!(deployment.name, "test");
        assert_eq!(deployment.provider, "openai");
        assert_eq!(deployment.model, "gpt-4");
    }

    #[test]
    fn test_deployment_with_options() {
        let deployment = Deployment::new("test", "openai", "gpt-4")
            .with_api_base("https://custom.api.com")
            .with_max_tokens(2000)
            .with_temperature(0.7);
        
        assert_eq!(deployment.api_base, Some("https://custom.api.com".to_string()));
        assert_eq!(deployment.max_tokens, Some(2000));
        assert_eq!(deployment.temperature, Some(0.7));
    }

    #[test]
    fn test_rate_limit_info_default() {
        let info = RateLimitInfo::default();
        assert_eq!(info.requests_per_minute, Some(60));
        assert_eq!(info.tokens_per_minute, Some(90000));
    }

    #[test]
    fn test_usage_stats() {
        let stats = UsageStats {
            requests_in_window: 10,
            tokens_in_window: 5000,
            remaining_requests: 50,
            remaining_tokens: 85000,
        };
        
        assert_eq!(stats.requests_in_window, 10);
        assert_eq!(stats.tokens_in_window, 5000);
        assert_eq!(stats.remaining_requests, 50);
        assert_eq!(stats.remaining_tokens, 85000);
    }
}
