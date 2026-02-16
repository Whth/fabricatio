//! Thryd - A lightweight, embedded LLM request router with caching.
//!
//! This library provides:
//! - Multi-provider LLM request routing
//! - Token usage tracking and rate limiting
//! - Persistent request caching
//! - Multiple routing strategies (round-robin, least-loaded, first-available)

pub mod cache;
pub mod connections;
pub mod constants;
pub mod error;
pub mod provider;
pub mod route;
pub mod tracker;

// Re-export commonly used types
pub use cache::{CacheConfig, CacheStats, PersistentCache};
pub use connections::{ClientConfig, ClientEntry, ConnectionStats};
pub use constants::*;
pub use error::{Result, ThrydError};
pub use provider::{
    Deployment, LlmProvider, Model, ProviderBuilder, RateLimitInfo, UsageStats,
};
pub use route::{
    RouteCandidate, RouteContext, Router, RouterBuilder, RoutingStrategy,
};
pub use tracker::{RequestInfo, UsageTracker};

/// Main configuration for thryd router
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ThrydConfig {
    /// Default routing strategy
    pub strategy: RoutingStrategy,
    /// Cache configuration
    pub cache: Option<CacheConfig>,
    /// Providers to register
    pub providers: Vec<ProviderConfig>,
}

/// Configuration for a single provider
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ProviderConfig {
    /// Provider name
    pub name: String,
    /// Provider type (openai, azure, anthropic, etc.)
    pub provider_type: String,
    /// Model name
    pub model: String,
    /// API base URL
    pub api_base: Option<String>,
    /// API key (should be loaded from environment)
    pub api_key: Option<String>,
    /// Priority (higher = preferred)
    pub priority: u32,
}

impl Default for ThrydConfig {
    fn default() -> Self {
        Self {
            strategy: RoutingStrategy::LeastLoaded,
            cache: None,
            providers: Vec::new(),
        }
    }
}

/// Initialize thryd with a configuration
pub async fn init(config: ThrydConfig) -> Result<Router> {
    let mut router = Router::new(config.strategy);

    // Add cache if configured
    if let Some(cache_config) = config.cache
        && let Some(path) = cache_config.persist_path {
        let cache = PersistentCache::open(path)
            .map_err(ThrydError::CacheIoError)?;
        router = router.with_cache(cache);
    }

    // Add providers
    for provider_config in config.providers {
        let api_key = provider_config.api_key.ok_or_else(|| {
            ThrydError::InvalidRequest(format!("API key required for provider: {}", provider_config.name))
        })?;

        let mut deployment = Deployment::new(
            provider_config.name.clone(),
            provider_config.provider_type,
            provider_config.model,
        )?;

        if let Some(base) = provider_config.api_base {
            deployment = deployment.with_api_base(base);
        }

        let provider = LlmProvider::new(deployment, api_key.into_boxed_str().into())?;
        router = router.add_provider(provider, provider_config.priority);
    }

    Ok(router)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thryd_config_default() {
        let config = ThrydConfig::default();
        assert_eq!(config.strategy, RoutingStrategy::LeastLoaded);
        assert!(config.cache.is_none());
        assert!(config.providers.is_empty());
    }

    #[test]
    fn test_provider_config() {
        let config = ProviderConfig {
            name: "test".into(),
            provider_type: "openai".into(),
            model: "gpt-4".into(),
            api_base: Some("https://api.openai.com/v1".into()),
            api_key: Some("test-key".into()),
            priority: 100,
        };

        assert_eq!(config.name, "test");
        assert_eq!(config.provider_type, "openai");
        assert_eq!(config.model, "gpt-4");
        assert_eq!(config.priority, 100);
    }
}
