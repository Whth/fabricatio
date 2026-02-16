use crate::cache::PersistentCache;
use crate::error::{Result, ThrydError};
use crate::provider::{LlmProvider, UsageStats};
use crate::tracker::count_token;
use serde::{Deserialize, Serialize};
use std::fmt::Debug;
use std::sync::Arc;

/// Routing strategy for selecting providers
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RoutingStrategy {
    /// Round-robin across available providers
    RoundRobin,
    /// Use provider with lowest current usage
    LeastLoaded,
    /// Use first available provider that can handle the request
    FirstAvailable,
}

/// A candidate provider with routing metadata
#[derive(Debug, Clone)]
pub struct RouteCandidate {
    pub provider: Arc<LlmProvider>,
    pub priority: u32,
}

/// Request context for routing decisions
#[derive(Debug, Clone)]
pub struct RouteContext {
    /// Estimated input tokens
    pub estimated_input_tokens: u32,
    /// Requested model (if any)
    pub model: Option<String>,
}

impl RouteContext {
    pub fn new() -> Self {
        Self {
            estimated_input_tokens: 0,
            model: None,
        }
    }

    pub fn with_tokens(mut self, tokens: u32) -> Self {
        self.estimated_input_tokens = tokens;
        self
    }

    pub fn with_model(mut self, model: impl Into<String>) -> Self {
        self.model = Some(model.into());
        self
    }
}

impl Default for RouteContext {
    fn default() -> Self {
        Self::new()
    }
}

/// Router for managing multiple LLM providers and routing requests
pub struct Router {
    candidates: Vec<RouteCandidate>,
    strategy: RoutingStrategy,
    cache: Option<PersistentCache>,
    round_robin_index: usize,
}

impl Router {
    /// Create a new router with the given strategy
    pub fn new(strategy: RoutingStrategy) -> Self {
        Self {
            candidates: Vec::new(),
            strategy,
            cache: None,
            round_robin_index: 0,
        }
    }

    /// Add a provider to the router
    pub fn add_provider(mut self, provider: LlmProvider, priority: u32) -> Self {
        self.candidates.push(RouteCandidate {
            provider: Arc::new(provider),
            priority,
        });
        // Sort by priority (higher first)
        self.candidates.sort_by_key(|b| std::cmp::Reverse(b.priority));
        self
    }

    /// Add multiple providers at once
    pub fn with_providers(mut self, providers: Vec<(LlmProvider, u32)>) -> Self {
        for (provider, priority) in providers {
            self = self.add_provider(provider, priority);
        }
        self
    }

    /// Enable persistent caching
    pub fn with_cache(mut self, cache: PersistentCache) -> Self {
        self.cache = Some(cache);
        self
    }

    /// Get current routing strategy
    pub fn strategy(&self) -> RoutingStrategy {
        self.strategy
    }

    /// Change routing strategy
    pub fn set_strategy(&mut self, strategy: RoutingStrategy) {
        self.strategy = strategy;
    }

    /// Get number of registered providers
    pub fn provider_count(&self) -> usize {
        self.candidates.len()
    }

    /// Get all providers
    pub fn providers(&self) -> Vec<Arc<LlmProvider>> {
        self.candidates.iter().map(|c| c.provider.clone()).collect()
    }

    /// Select the best provider based on current strategy
    pub async fn select_provider(&mut self, context: &RouteContext) -> Result<Arc<LlmProvider>> {
        if self.candidates.is_empty() {
            return Err(ThrydError::NoProviderFound {
                model: context.model.clone().unwrap_or_default(),
            });
        }

        match self.strategy {
            RoutingStrategy::RoundRobin => self.select_round_robin(context).await,
            RoutingStrategy::LeastLoaded => self.select_least_loaded(context).await,
            RoutingStrategy::FirstAvailable => self.select_first_available(context).await,
        }
    }

    /// Round-robin selection
    async fn select_round_robin(&mut self, _context: &RouteContext) -> Result<Arc<LlmProvider>> {
        if self.candidates.is_empty() {
            return Err(ThrydError::InvalidRequest("No providers available".to_string()));
        }

        let index = self.round_robin_index % self.candidates.len();
        self.round_robin_index += 1;

        Ok(self.candidates[index].provider.clone())
    }

    /// Select provider with lowest current usage
    async fn select_least_loaded(&self, context: &RouteContext) -> Result<Arc<LlmProvider>> {
        let mut best_provider: Option<Arc<LlmProvider>> = None;
        let mut best_score: Option<u64> = None;

        for candidate in &self.candidates {
            let can_handle = candidate.provider.can_handle(context.estimated_input_tokens).await;

            if can_handle {
                let stats = candidate.provider.usage_stats().await;
                // Lower score is better - combine requests and tokens
                let score = (stats.requests_in_window as u64) * 1000 + stats.tokens_in_window as u64;

                if best_score.is_none() || score < best_score.unwrap() {
                    best_score = Some(score);
                    best_provider = Some(candidate.provider.clone());
                }
            }
        }

        best_provider.ok_or_else(|| ThrydError::NoProviderFound {
            model: context.model.clone().unwrap_or_default(),
        })
    }

    /// Select first provider that can handle the request
    async fn select_first_available(&self, context: &RouteContext) -> Result<Arc<LlmProvider>> {
        for candidate in &self.candidates {
            if candidate.provider.can_handle(context.estimated_input_tokens).await {
                return Ok(candidate.provider.clone());
            }
        }

        Err(ThrydError::NoProviderFound {
            model: context.model.clone().unwrap_or_default(),
        })
    }

    /// Route a request and execute it with caching support
    pub async fn route_and_execute(
        &mut self,
        context: &RouteContext,
        prompt: &str,
    ) -> Result<serde_json::Value> {
        // Check cache if available
        if let Some(ref cache) = self.cache {
            let model = context.model.as_deref().unwrap_or("default");
            let key = PersistentCache::generate_key(prompt, model);

            if let Some(cached) = cache.get(&key) {
                return serde_json::from_str(&cached).map_err(ThrydError::JsonError);
            }
        }

        // Select provider
        let provider = self.select_provider(context).await?;

        // Execute request
        let response = provider.completion(serde_json::json!({
            "model": provider.deployment().model,
            "messages": [{"role": "user", "content": prompt}]
        })).await?;

        // Record usage
        let input_tokens = count_token(prompt.to_string());
        provider.record_usage(input_tokens, 0).await;

        // Cache response if enabled
        if let Some(ref cache) = self.cache {
            let model = context.model.as_deref().unwrap_or("default");
            let key = PersistentCache::generate_key(prompt, model);
            cache.set(&key, response.to_string());
        }

        Ok(response)
    }

    /// Get usage stats for all providers
    pub async fn all_usage_stats(&self) -> Vec<(String, UsageStats)> {
        let mut stats = Vec::new();
        for candidate in &self.candidates {
            let provider_stats = candidate.provider.usage_stats().await;
            stats.push((candidate.provider.name().to_string(), provider_stats));
        }
        stats
    }

    /// Wait for a provider to become available
    pub async fn wait_for_provider(
        &self,
        context: &RouteContext,
        max_wait_ms: u64,
    ) -> Result<Arc<LlmProvider>> {
        let start = std::time::Instant::now();

        while (start.elapsed().as_millis() as u64) < max_wait_ms {
            for candidate in &self.candidates {
                if candidate.provider.can_handle(context.estimated_input_tokens).await {
                    return Ok(candidate.provider.clone());
                }
            }

            // Wait a bit before retrying
            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        }

        let reason = format!("No provider available within {}ms", max_wait_ms);
        Err(ThrydError::ProviderUnavailable {
            provider: "any".to_string(),
            reason,
        })
    }
}

impl Debug for Router {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Router")
            .field("strategy", &self.strategy)
            .field("candidates", &self.candidates.len())
            .field("cache_enabled", &self.cache.is_some())
            .finish()
    }
}

/// Builder for creating Router instances
pub struct RouterBuilder {
    strategy: RoutingStrategy,
    providers: Vec<(LlmProvider, u32)>,
    cache: Option<PersistentCache>,
}

impl RouterBuilder {
    pub fn new() -> Self {
        Self {
            strategy: RoutingStrategy::LeastLoaded,
            providers: Vec::new(),
            cache: None,
        }
    }

    pub fn strategy(mut self, strategy: RoutingStrategy) -> Self {
        self.strategy = strategy;
        self
    }

    pub fn add_provider(mut self, provider: LlmProvider, priority: u32) -> Self {
        self.providers.push((provider, priority));
        self
    }

    pub fn with_cache(mut self, cache: PersistentCache) -> Self {
        self.cache = Some(cache);
        self
    }

    pub fn build(self) -> Router {
        let mut router = Router::new(self.strategy);
        router = router.with_providers(self.providers);
        if let Some(cache) = self.cache {
            router = router.with_cache(cache);
        }
        router
    }
}

impl Default for RouterBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_route_context() {
        let ctx = RouteContext::new();
        assert_eq!(ctx.estimated_input_tokens, 0);
        assert!(ctx.model.is_none());

        let ctx = RouteContext::new()
            .with_tokens(100)
            .with_model("gpt-4");
        
        assert_eq!(ctx.estimated_input_tokens, 100);
        assert_eq!(ctx.model, Some("gpt-4".to_string()));
    }

    #[test]
    fn test_routing_strategy_default() {
        let strategy = RoutingStrategy::LeastLoaded;
        assert_eq!(format!("{:?}", strategy), "LeastLoaded");
    }

    #[test]
    fn test_router_new() {
        let router = Router::new(RoutingStrategy::RoundRobin);
        assert_eq!(router.provider_count(), 0);
        assert_eq!(router.strategy(), RoutingStrategy::RoundRobin);
    }

    #[test]
    fn test_router_builder() {
        let builder = RouterBuilder::new();
        assert_eq!(builder.strategy, RoutingStrategy::LeastLoaded);
        assert!(builder.providers.is_empty());
        assert!(builder.cache.is_none());

        let builder = RouterBuilder::new()
            .strategy(RoutingStrategy::RoundRobin);
        assert_eq!(builder.strategy, RoutingStrategy::RoundRobin);
    }
}
