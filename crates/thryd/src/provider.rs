use crate::error::{Result, ThrydError};
use crate::tracker::UsageTracker;
use async_trait::async_trait;
use secrecy::SecretString;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fmt::Debug;
use std::str::FromStr;
use std::sync::Arc;
use std::time::Duration;
use strum::EnumString;
use tokio::sync::RwLock;

// =============================================================================
// Provider Type & Defaults
// =============================================================================

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize, EnumString)]
pub enum ProviderType {
    OpenAI,
    Anthropic,
    AzureOpenAI,
    Ollama,
    Custom(String),
}

impl ProviderType {
    pub fn as_str(&self) -> &str {
        match self {
            ProviderType::OpenAI => "openai",
            ProviderType::Anthropic => "anthropic",
            ProviderType::AzureOpenAI => "azure",
            ProviderType::Ollama => "ollama",
            ProviderType::Custom(name) => name,
        }
    }

    pub fn default_api_base(&self) -> Option<&'static str> {
        match self {
            ProviderType::OpenAI => Some("https://api.openai.com/v1"),
            ProviderType::Anthropic => Some("https://api.anthropic.com/v1"),
            ProviderType::AzureOpenAI => None, // Must be provided
            ProviderType::Ollama => Some("http://localhost:11434/api"),
            ProviderType::Custom(_) => None,
        }
    }

    pub fn chat_endpoint(&self) -> &'static str {
        match self {
            ProviderType::OpenAI | ProviderType::AzureOpenAI => "/chat/completions",
            ProviderType::Anthropic => "/messages",
            ProviderType::Ollama => "/chat",
            ProviderType::Custom(_) => "/chat/completions",
        }
    }
}

// =============================================================================
// Generation Config
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationConfig {
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
    pub max_tokens: Option<u32>,
    pub stop: Option<Vec<String>>,
    pub presence_penalty: Option<f32>,
    pub frequency_penalty: Option<f32>,
    pub stream: Option<bool>,
}

impl Default for GenerationConfig {
    fn default() -> Self {
        Self {
            temperature: Some(0.7),
            top_p: Some(1.0),
            max_tokens: Some(2048),
            stop: None,
            presence_penalty: Some(0.0),
            frequency_penalty: Some(0.0),
            stream: Some(false),
        }
    }
}

// =============================================================================
// Cache Preference
// =============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum CachePreference {
    #[default]
    Default,
    Enabled,
    Disabled,
}

// =============================================================================
// Completion Options
// =============================================================================

#[derive(Debug, Clone, Default)]
pub struct CompletionOptions {
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
    pub max_tokens: Option<u32>,
    pub stop: Option<Vec<String>>,
    pub presence_penalty: Option<f32>,
    pub frequency_penalty: Option<f32>,
    pub stream: Option<bool>,
    pub cache: CachePreference,
}

impl CompletionOptions {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_temperature(mut self, temperature: f32) -> Self {
        self.temperature = Some(temperature);
        self
    }

    pub fn with_top_p(mut self, top_p: f32) -> Self {
        self.top_p = Some(top_p);
        self
    }

    pub fn with_max_tokens(mut self, max_tokens: u32) -> Self {
        self.max_tokens = Some(max_tokens);
        self
    }

    pub fn with_stop(mut self, stop: Vec<String>) -> Self {
        self.stop = Some(stop);
        self
    }

    pub fn with_presence_penalty(mut self, presence_penalty: f32) -> Self {
        self.presence_penalty = Some(presence_penalty);
        self
    }

    pub fn with_frequency_penalty(mut self, frequency_penalty: f32) -> Self {
        self.frequency_penalty = Some(frequency_penalty);
        self
    }

    pub fn with_stream(mut self, stream: bool) -> Self {
        self.stream = Some(stream);
        self
    }

    pub fn with_cache(mut self) -> Self {
        self.cache = CachePreference::Enabled;
        self
    }

    pub fn without_cache(mut self) -> Self {
        self.cache = CachePreference::Disabled;
        self
    }
}

// =============================================================================
// Deployment
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Deployment {
    pub name: String,
    pub provider_type: ProviderType,
    pub model: String,
    pub api_base: Option<String>,
    pub generation_config: GenerationConfig,
}

impl Deployment {
    pub fn new(name: impl Into<String>, provider: impl AsRef<str>, model: impl Into<String>) -> Result<Self> {
        let provider_type = ProviderType::from_str(provider.as_ref())?;
        Ok(Self {
            name: name.into(),
            provider_type,
            model: model.into(),
            api_base: None,
            generation_config: GenerationConfig::default(),
        }
        )
    }

    pub fn with_api_base(mut self, api_base: impl Into<String>) -> Self {
        self.api_base = Some(api_base.into());
        self
    }

    pub fn with_generation_config(mut self, config: GenerationConfig) -> Self {
        self.generation_config = config;
        self
    }

    pub fn with_temperature(mut self, temperature: f32) -> Self {
        self.generation_config.temperature = Some(temperature);
        self
    }

    pub fn with_top_p(mut self, top_p: f32) -> Self {
        self.generation_config.top_p = Some(top_p);
        self
    }

    pub fn with_max_tokens(mut self, max_tokens: u32) -> Self {
        self.generation_config.max_tokens = Some(max_tokens);
        self
    }

    pub fn with_stop(mut self, stop: Vec<String>) -> Self {
        self.generation_config.stop = Some(stop);
        self
    }

    pub fn with_presence_penalty(mut self, presence_penalty: f32) -> Self {
        self.generation_config.presence_penalty = Some(presence_penalty);
        self
    }

    pub fn with_frequency_penalty(mut self, frequency_penalty: f32) -> Self {
        self.generation_config.frequency_penalty = Some(frequency_penalty);
        self
    }

    pub fn with_stream(mut self, stream: bool) -> Self {
        self.generation_config.stream = Some(stream);
        self
    }
}

// =============================================================================
// Rate Limit & Usage Stats
// =============================================================================

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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageStats {
    pub requests_in_window: u32,
    pub tokens_in_window: u32,
    pub remaining_requests: u32,
    pub remaining_tokens: u32,
}

// =============================================================================
// LLM Provider
// =============================================================================

pub struct LlmProvider {
    name: String,
    deployment: Deployment,
    http_client: reqwest::Client,
    rate_limit: RateLimitInfo,
    usage_tracker: Arc<RwLock<UsageTracker>>,
    generation_config: GenerationConfig,
    cache_enabled: bool,
}

impl Debug for LlmProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("LlmProvider")
            .field("name", &self.name)
            .field("deployment", &self.deployment)
            .field("generation_config", &self.generation_config)
            .field("cache_enabled", &self.cache_enabled)
            .finish()
    }
}

impl LlmProvider {
    pub fn new(deployment: Deployment, api_key: SecretString) -> Result<Self> {
        Self::with_api_base(deployment, api_key, None)
    }

    pub fn with_api_base(
        deployment: Deployment,
        _api_key: SecretString,
        api_base_override: Option<String>,
    ) -> Result<Self> {
        let _resolved_api_base = api_base_override
            .or_else(|| deployment.api_base.clone())
            .or_else(|| {
                deployment
                    .provider_type
                    .default_api_base()
                    .map(|s| s.to_string())
            })
            .ok_or_else(|| {
                ThrydError::ConfigurationError(
                    "No API base URL provided and no default available for this provider".into(),
                )
            })?;

        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|e| ThrydError::ConfigurationError(format!("Failed to create HTTP client: {}", e)))?;

        let rate_limit = RateLimitInfo::default();

        let usage_tracker = Arc::new(RwLock::new(UsageTracker::new(
            rate_limit.tokens_per_minute.unwrap_or(90000),
            rate_limit.requests_per_minute.unwrap_or(60),
            60_000,
        )));

        Ok(Self {
            name: deployment.name.clone(),
            deployment,
            http_client: client,
            rate_limit,
            usage_tracker,
            generation_config: GenerationConfig::default(),
            cache_enabled: true,
        })
    }

    pub fn set_cache_enabled(&mut self, enabled: bool) {
        self.cache_enabled = enabled;
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn deployment(&self) -> &Deployment {
        &self.deployment
    }

    pub fn rate_limit(&self) -> &RateLimitInfo {
        &self.rate_limit
    }

    pub async fn can_handle(&self, estimated_tokens: u32) -> bool {
        let tracker = self.usage_tracker.read().await;
        tracker.can_make_request(estimated_tokens)
    }

    pub async fn estimated_wait_time(&self, estimated_tokens: u32) -> u64 {
        let tracker = self.usage_tracker.read().await;
        tracker.estimated_waiting_time_for_tokens(estimated_tokens)
    }

    pub async fn record_usage(&self, input_tokens: u32, output_tokens: u32) {
        let mut tracker = self.usage_tracker.write().await;
        tracker.add_request(input_tokens, output_tokens);
    }

    pub async fn usage_stats(&self) -> UsageStats {
        let tracker = self.usage_tracker.read().await;
        UsageStats {
            requests_in_window: tracker.request_usage(),
            tokens_in_window: tracker.token_usage() as u32,
            remaining_requests: tracker.remaining_requests().unwrap_or(0),
            remaining_tokens: tracker.remaining_tokens().unwrap_or(0) as u32,
        }
    }

    fn should_use_cache(&self, cache_preference: CachePreference) -> bool {
        match cache_preference {
            CachePreference::Enabled => true,
            CachePreference::Disabled => false,
            CachePreference::Default => self.cache_enabled,
        }
    }

    fn build_request_body(&self, messages: Vec<Value>, options: &CompletionOptions) -> Value {
        let mut body = json!({
            "model": self.deployment.model,
            "messages": messages,
        });

        if let Some(temp) = options.temperature.or(self.generation_config.temperature) {
            body["temperature"] = json!(temp);
        }
        if let Some(top_p) = options.top_p.or(self.generation_config.top_p) {
            body["top_p"] = json!(top_p);
        }
        if let Some(max_tokens) = options.max_tokens.or(self.generation_config.max_tokens) {
            body["max_tokens"] = json!(max_tokens);
        }
        if let Some(stop) = options.stop.as_ref().or(self.generation_config.stop.as_ref()) {
            body["stop"] = json!(stop);
        }
        if let Some(presence_penalty) = options.presence_penalty.or(self.generation_config.presence_penalty) {
            body["presence_penalty"] = json!(presence_penalty);
        }
        if let Some(frequency_penalty) = options.frequency_penalty.or(self.generation_config.frequency_penalty) {
            body["frequency_penalty"] = json!(frequency_penalty);
        }
        if let Some(stream) = options.stream.or(self.generation_config.stream) {
            body["stream"] = json!(stream);
        }

        body
    }

    pub async fn chat_with_options(&self, messages: Vec<Value>, options: CompletionOptions) -> Result<Value> {
        let request_body = self.build_request_body(messages, &options);

        let base_url = self.deployment.api_base.clone()
            .or_else(|| {
                self.deployment
                    .provider_type
                    .default_api_base()
                    .map(|s| s.to_string())
            })
            .ok_or_else(|| ThrydError::ConfigurationError("API base URL not configured".to_string()))?;

        let endpoint = self.deployment.provider_type.chat_endpoint();
        let url = format!("{}{}", base_url.trim_end_matches('/'), endpoint);

        let mut request_builder = self.http_client
            .post(&url)
            .header("Content-Type", "application/json");

        if !self.should_use_cache(options.cache) {
            request_builder = request_builder.header("Cache-Control", "no-cache");
        }

        let response = request_builder
            .json(&request_body)
            .send()
            .await
            .map_err(|e| ThrydError::ApiError(format!("Failed to send request: {}", e)))?;

        let response_json: Value = response.json().await
            .map_err(|e| ThrydError::ApiError(format!("Failed to parse response: {}", e)))?;

        Ok(response_json)
    }

    pub async fn chat(&self, messages: Vec<Value>) -> Result<Value> {
        self.chat_with_options(messages, CompletionOptions::default()).await
    }

    pub async fn completion_with_options(&self, mut request: Value, options: CompletionOptions) -> Result<Value> {
        if let Some(obj) = request.as_object_mut() {
            if let Some(temp) = options.temperature.or(self.generation_config.temperature) {
                obj.insert("temperature".to_string(), json!(temp));
            }
            if let Some(top_p) = options.top_p.or(self.generation_config.top_p) {
                obj.insert("top_p".to_string(), json!(top_p));
            }
            if let Some(max_tokens) = options.max_tokens.or(self.generation_config.max_tokens) {
                obj.insert("max_tokens".to_string(), json!(max_tokens));
            }
        }

        let base_url = self.deployment.api_base.clone()
            .or_else(|| {
                self.deployment
                    .provider_type
                    .default_api_base()
                    .map(|s| s.to_string())
            })
            .ok_or_else(|| ThrydError::ConfigurationError("API base URL not configured".to_string()))?;

        let endpoint = self.deployment.provider_type.chat_endpoint();
        let url = format!("{}{}", base_url.trim_end_matches('/'), endpoint);

        let mut request_builder = self.http_client
            .post(&url)
            .header("Content-Type", "application/json");

        if !self.should_use_cache(options.cache) {
            request_builder = request_builder.header("Cache-Control", "no-cache");
        }

        let response = request_builder
            .json(&request)
            .send()
            .await
            .map_err(|e| ThrydError::ApiError(format!("Failed to send request: {}", e)))?;

        let response_json: Value = response.json().await
            .map_err(|e| ThrydError::ApiError(format!("Failed to parse response: {}", e)))?;

        Ok(response_json)
    }

    pub async fn completion(&self, request: Value) -> Result<Value> {
        self.completion_with_options(request, CompletionOptions::default()).await
    }
}

#[async_trait]
impl Model for LlmProvider {
    fn name(&self) -> &str {
        &self.name
    }

    fn provider(&self) -> &str {
        self.deployment.provider_type.as_str()
    }

    async fn completion(&self, request: Value) -> Result<Value> {
        self.completion(request).await
    }

    async fn completion_with_options(&self, request: Value, options: CompletionOptions) -> Result<Value> {
        self.completion_with_options(request, options).await
    }

    fn client(&self) -> &dyn std::any::Any {
        self
    }

    fn generation_config(&self) -> &GenerationConfig {
        &self.generation_config
    }

    fn set_generation_config(&mut self, config: GenerationConfig) {
        self.generation_config = config;
    }
}

// =============================================================================
// Model Trait
// =============================================================================

#[async_trait]
pub trait Model: Send + Sync {
    fn name(&self) -> &str;
    fn provider(&self) -> &str;
    async fn completion(&self, request: Value) -> Result<Value>;
    async fn completion_with_options(&self, request: Value, options: CompletionOptions) -> Result<Value>;
    fn client(&self) -> &dyn std::any::Any;
    fn generation_config(&self) -> &GenerationConfig;
    fn set_generation_config(&mut self, config: GenerationConfig);
}

// =============================================================================
// Provider Builder
// =============================================================================

pub struct ProviderBuilder {
    deployment: Deployment,
    api_key: Option<SecretString>,
    api_base: Option<String>,
    rate_limit: Option<RateLimitInfo>,
    generation_config: Option<GenerationConfig>,
    cache_enabled: bool,
}

impl ProviderBuilder {
    pub fn new(name: impl Into<String>, provider: impl AsRef<str>, model: impl Into<String>) -> Result<Self> {
        Ok(Self {
            deployment: Deployment::new(name, provider, model)?,
            api_key: None,
            api_base: None,
            rate_limit: None,
            generation_config: None,
            cache_enabled: true,
        }
        )
    }

    pub fn with_api_key(mut self, api_key: impl Into<String>) -> Self {
        self.api_key = Some(SecretString::new(api_key.into().into_boxed_str()));
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

    pub fn with_generation_config(mut self, config: GenerationConfig) -> Self {
        self.generation_config = Some(config.clone());
        self.deployment.generation_config = config;
        self
    }

    pub fn with_temperature(mut self, temperature: f32) -> Self {
        self.deployment = self.deployment.with_temperature(temperature);
        self
    }

    pub fn with_max_tokens(mut self, max_tokens: u32) -> Self {
        self.deployment = self.deployment.with_max_tokens(max_tokens);
        self
    }

    pub fn with_cache_enabled(mut self, enabled: bool) -> Self {
        self.cache_enabled = enabled;
        self
    }

    pub fn build(self) -> Result<LlmProvider> {
        let api_key = self.api_key.ok_or_else(|| {
            ThrydError::InvalidRequest("API key is required".to_string())
        })?;

        let mut provider = LlmProvider::with_api_base(self.deployment, api_key, self.api_base)?;

        if let Some(rl) = self.rate_limit {
            provider.rate_limit = rl;
        }

        if let Some(config) = self.generation_config {
            provider.generation_config = config;
        }

        provider.cache_enabled = self.cache_enabled;

        Ok(provider)
    }
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deployment_new() {
        let deployment = Deployment::new("test", "openai", "gpt-4");
        assert!(!deployment.is_err());
        let deployment = deployment.unwrap();
        assert_eq!(deployment.name, "test");
        assert_eq!(deployment.provider_type, ProviderType::OpenAI);
        assert_eq!(deployment.model, "gpt-4");
    }

    #[test]
    fn test_deployment_with_options() {
        let deployment = Deployment::new("test", "openai", "gpt-4")
            .unwrap()
            .with_api_base("https://custom.api.com")
            .with_temperature(0.7)
            .with_max_tokens(2000)
            .with_top_p(0.9)
            .with_presence_penalty(0.5);

        assert_eq!(deployment.api_base, Some("https://custom.api.com".to_string()));
        assert_eq!(deployment.generation_config.temperature, Some(0.7));
        assert_eq!(deployment.generation_config.max_tokens, Some(2000));
        assert_eq!(deployment.generation_config.top_p, Some(0.9));
        assert_eq!(deployment.generation_config.presence_penalty, Some(0.5));
    }

    #[test]
    fn test_completion_options() {
        let options = CompletionOptions::new()
            .with_temperature(0.8)
            .with_max_tokens(1000)
            .with_top_p(0.95)
            .without_cache();

        assert_eq!(options.temperature, Some(0.8));
        assert_eq!(options.max_tokens, Some(1000));
        assert_eq!(options.top_p, Some(0.95));
        assert_eq!(options.cache, CachePreference::Disabled);

        let options_with_cache = CompletionOptions::new().with_cache();
        assert_eq!(options_with_cache.cache, CachePreference::Enabled);
    }

    #[test]
    fn test_provider_type_defaults() {
        assert_eq!(ProviderType::OpenAI.default_api_base(), Some("https://api.openai.com/v1"));
        assert_eq!(ProviderType::Anthropic.default_api_base(), Some("https://api.anthropic.com/v1"));
        assert_eq!(ProviderType::Ollama.default_api_base(), Some("http://localhost:11434/api"));
        assert_eq!(ProviderType::AzureOpenAI.default_api_base(), None);
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