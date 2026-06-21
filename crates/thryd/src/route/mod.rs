//! # Request Routing System
//!
//! This module provides the [`Router`] for managing LLM providers, deployments,
//! and routing requests with built-in caching and load balancing.
//!
//! ## Architecture
//!
//! - **Providers**: API backends (OpenAI-compatible, etc.) registered with the router
//! - **Deployments**: Models wrapped with rate limiting and quota tracking
//! - **Groups**: Named collections of deployments for load-balanced routing
//!
//! ## Routing Strategy
//!
//! The router uses a **least-loaded-first** strategy with **first-available** fallback:
//!
//! 1. Iterate all deployments in the target group
//! 2. Find the deployment with minimum cooldown time (load)
//! 3. If a deployment has zero wait time (available), use it immediately
//! 4. Otherwise, select the deployment with lowest projected wait time
//!
//! ## Caching
//!
//! The router supports optional persistent caching via `blake3` hash keys.
//! Cache hits return immediately without calling the model.
//!
//! # Example: Completion Router
//!
//! ```ignore
//! use thryd::{Router, CompletionTag, CompletionRequest};
//! use thryd::provider::OpenaiCompatible;
//! use secrecy::SecretString;
//! use std::sync::Arc;
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     let mut router = Router::<CompletionTag>::default();
//!     router.add_provider(Arc::new(OpenaiCompatible::openai(
//!         SecretString::from("sk-...")
//!     )))?;
//!     router.deploy("default", "openai/gpt-4".into(), Some(60), Some(100_000))?;
//!
//!     let response = router.invoke("default".into(), CompletionRequest {
//!         message: "Hello!".into(),
//!         stream: false,
//!         top_p: None, temperature: None,
//!         max_completion_tokens: Some(100),
//!         presence_penalty: None, frequency_penalty: None,
//!     }).await?;
//!     println!("{}", response);
//!     Ok(())
//! }
//! ```
//!
//! # Example: Embedding Router
//!
//! ```ignore
//! use thryd::{Router, EmbeddingTag, EmbeddingRequest};
//!
//! let mut router = Router::<EmbeddingTag>::with_cache("./cache.db")?;
//! // ... add providers and deployments ...
//!
//! let embeddings = router.invoke("embed".into(), EmbeddingRequest {
//!     texts: vec!["hello world".into(), "goodbye world".into()]
//! }).await?;
//! ```

mod retry;
mod tag;

// Re-export public types from submodules
pub use retry::RetryConfig;
pub use tag::{CacheKey, CompletionTag, EmbeddingTag, ModelTypeTag, RerankerTag};

use crate::deployment::Deployment;
use crate::provider::Provider;
use crate::tracker::Quota;
use crate::utils::analyze_identifier;
use crate::{PersistentCache, Result, ThrydError};
use dashmap::DashMap;
use dashmap::mapref::one::Ref;
use std::path::Path;
use std::sync::Arc;
use tracing::*;

use retry::retry_on_transient;

/// Unique identifier for a deployment, format: `"{provider_name}{SEPARATE}{model_name}"`.
pub type DeploymentIdentifier = String;

/// Name for a group of deployments. Requests routed by group name.
pub type RouteGroupName = String;

/// Unique name identifying a provider.
pub type ProviderName = String;

/// Name of a model within its provider.
pub type ModelName = String;

/// Shared reference to a deployment with a specific model type.
pub type DeploymentEntry<Model> = Arc<Deployment<Model>>;

/// Request router with caching and multi-provider support.
///
/// Manages providers, deployments organized in groups, and routes requests
/// using the least-loaded-first strategy. Supports optional persistent caching
/// keyed by request content hash.
///
/// # Type Parameters
///
/// * `Tag` - A [`ModelTypeTag`] implementing the request/response types and model creation
///
/// # Providers
///
/// Providers must be added via [`add_or_update_provider`](Self::add_or_update_provider)
/// before deploying models that require them.
///
/// # Deployments
///
/// Deployments are created implicitly via [`deploy`](Self::deploy), wrapping a
/// model from a provider with optional rate limits (RPM/TPM quotas).
///
/// # Groups
///
/// Groups organize deployments for routing. The same group name can be used
/// across multiple deployments for load balancing.
///
/// # Caching
///
/// Cache is optional and initialized via [`with_cache`](Self::with_cache).
/// When enabled, identical requests (same input text hash) return cached results.
///
/// # Thread Safety
///
/// All operations are safe across threads via internal `DashMap` usage.
pub struct Router<Tag: ModelTypeTag> {
    /// Optional persistent cache for request deduplication.
    /// `None` when caching is disabled.
    cache: Option<PersistentCache>,

    /// Registered providers by name. Thread-safe concurrent map.
    providers: DashMap<ProviderName, Arc<dyn Provider>>,

    /// Deployment groups by name. Each group contains deployments for routing.
    groups: DashMap<RouteGroupName, Vec<DeploymentEntry<Tag::Model>>>,

    /// Retry configuration for transient failures. `None` disables retries.
    retry: std::sync::RwLock<Option<RetryConfig>>,
}

impl<Tag: ModelTypeTag> Router<Tag> {
    /// Create a router with persistent caching enabled.
    ///
    /// # Arguments
    /// * `database_file` - Path to the LMDB cache database directory.
    ///   Created automatically if it doesn't exist.
    ///
    /// # Returns
    /// A new `Router` instance with caching initialized.
    ///
    /// # Example
    ///
    /// ```ignore
    /// let router = Router::<CompletionTag>::with_cache("./llm-cache")?;
    /// ```
    pub fn with_cache(database_file: impl AsRef<Path>) -> Result<Self> {
        Ok(Self {
            cache: Some(PersistentCache::create_or_open(database_file)?),
            ..Self::default()
        })
    }

    /// Enable automatic retry on transient failures with the given configuration.
    ///
    /// # Arguments
    /// * `config` - Retry policy (max retries, backoff parameters).
    pub fn with_retry(self, config: RetryConfig) -> Self {
        *self.retry.write().unwrap() = Some(config);
        self
    }

    /// Update the retry configuration at runtime.
    ///
    /// Pass `None` to disable retries.
    pub fn set_retry(&self, config: Option<RetryConfig>) {
        *self.retry.write().unwrap() = config;
    }

    /// Register or update a provider in the router.
    ///
    /// If a provider with the same name exists, it is replaced.
    ///
    /// # Arguments
    /// * `provider` - The provider instance to register
    ///
    /// # Returns
    /// Self for method chaining.
    ///
    /// # Example
    ///
    /// ```ignore
    /// router.add_or_update_provider(openai_provider.clone());
    /// router.add_or_update_provider(azure_provider.clone());
    /// ```
    pub fn add_or_update_provider(&self, provider: Arc<dyn Provider>) -> &Self {
        debug!(
            "Insert provider `{}`, base_url: `{}`",
            provider.provider_name(),
            provider.endpoint()
        );
        self.providers
            .insert(provider.provider_name().to_string(), provider);
        self
    }

    /// Remove a provider from the router.
    ///
    /// # Arguments
    /// * `provider_name` - Name of the provider to remove
    ///
    /// # Returns
    /// * `Ok(self)` on successful removal
    /// * `Err(ThrydError::Router)` if the provider was not registered
    pub fn remove_provider(&self, provider_name: &str) -> Result<&Self> {
        debug!("Removing provider `{}`", provider_name);
        self.providers.remove(provider_name).ok_or_else(|| {
            ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
        })?;
        Ok(self)
    }

    /// Add a deployment to a group.
    ///
    /// # Arguments
    /// * `group` - Name of the group to add the deployment to
    /// * `deployment` - The deployment to add
    pub fn add_deployment(
        &self,
        group: RouteGroupName,
        deployment: Deployment<Tag::Model>,
    ) -> Result<&Self> {
        debug!(
            "Adding deployment `{}` to group `{}`",
            deployment.identifier(),
            group
        );
        self.groups
            .entry(group)
            .or_default()
            .push(Arc::new(deployment));
        Ok(self)
    }

    /// Remove a specific deployment from a group.
    ///
    /// # Arguments
    /// * `group` - Name of the group to remove from
    /// * `deployment_identifier` - Identifier of the deployment to remove
    pub fn remove_deployment(
        &self,
        group: &str,
        deployment_identifier: DeploymentIdentifier,
    ) -> Result<&Self> {
        debug!(
            "Removing deployment `{}` from group `{}`",
            deployment_identifier, group
        );
        self.groups
            .get_mut(group)
            .ok_or_else(|| {
                ThrydError::Router(format!("Group with name `{}` is not added.", group))
            })?
            .retain(|deployment| deployment.identifier() != deployment_identifier);
        Ok(self)
    }

    /// Deploy a model to a group with optional rate limits.
    ///
    /// Creates a deployment by looking up the provider in the identifier string
    /// (format: `"{provider_name}{SEPARATE}{model_name}"`) and wrapping the model
    /// with the specified RPM/TPM quotas.
    ///
    /// # Arguments
    /// * `group` - Name of the group to deploy to. Created if doesn't exist.
    /// * `deployment_identifier` - Model identifier in `provider{model}` format.
    /// * `rpm` - Optional requests-per-minute quota limit.
    /// * `tpm` - Optional tokens-per-minute quota limit.
    ///
    /// # Returns
    /// * `Ok(self)` on success
    /// * `Err(ThrydError::Router)` if the provider was not found
    ///
    /// # Example
    ///
    /// ```ignore
    /// // Deploy GPT-4 from OpenAI to the "chat" group
    /// router.deploy(
    ///     "chat".into(),
    ///     "openai/gpt-4".into(),
    ///     Some(60),   // 60 RPM
    ///     Some(100_000), // 100k TPM
    /// )?;
    ///
    /// // Deploy Claude to the same group for load balancing
    /// router.deploy(
    ///     "chat".into(),
    ///     "anthropic/claude-3".into(),
    ///     Some(20),   // 20 RPM
    ///     Some(50_000), // 50k TPM
    /// )?;
    /// ```
    pub fn deploy(
        &self,
        group: RouteGroupName,
        deployment_identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> Result<&Self> {
        debug!("Deploying `{}` to group `{}`", deployment_identifier, group);
        let d = self.create_deployment(deployment_identifier, rpm, tpm)?;

        self.add_deployment(group, d)
    }

    /// Remove a model deployment from a group.
    ///
    /// # Arguments
    /// * `group` - Name of the group to remove from
    /// * `deployment_identifier` - Identifier of the deployment to remove
    ///
    /// # Returns
    /// * `Ok(self)` on success
    /// * `Err(ThrydError::Router)` if the group or deployment was not found
    pub fn undeploy(
        &self,
        group: RouteGroupName,
        deployment_identifier: DeploymentIdentifier,
    ) -> Result<&Self> {
        debug!(
            "Undeploying `{}` to group `{}`",
            deployment_identifier, group
        );

        self.remove_deployment(group.as_str(), deployment_identifier)
    }

    /// Remove an entire group and all its deployments.
    ///
    /// # Arguments
    /// * `group` - Name of the group to remove
    ///
    /// # Returns
    /// * `Ok(self)` on success
    /// * `Err(ThrydError::Router)` if the group was not found
    pub fn remove_group(&self, group: &str) -> Result<&Self> {
        debug!("Removing group `{}`", group);
        self.groups.remove(group).ok_or_else(|| {
            ThrydError::Router(format!("Group with name `{}` is not added.", group))
        })?;

        Ok(self)
    }

    /// Get a reference to a group's deployment list.
    pub fn get_group(
        &self,
        group: RouteGroupName,
    ) -> Result<Ref<'_, RouteGroupName, Vec<DeploymentEntry<Tag::Model>>>> {
        self.groups
            .get(group.as_str())
            .ok_or_else(|| ThrydError::Router(format!("Group with name `{}` is not added.", group)))
    }

    /// Wait for any available deployment in the group.
    ///
    /// Implements the **least-loaded-first** routing strategy:
    /// - Finds deployments with zero cooldown time (immediately available)
    /// - Falls back to the deployment with minimum projected wait time
    ///
    /// # Arguments
    /// * `group` - Name of the group to route to
    /// * `token_count` - Token count for TPM calculation
    ///
    /// # Returns
    /// * `Ok(DeploymentEntry)` - The selected deployment
    /// * `Err(ThrydError::Router)` - If no deployments exist in the group
    async fn wait_for_any(
        &self,
        group: RouteGroupName,
        token_count: u64,
    ) -> Result<DeploymentEntry<Tag::Model>> {
        let mut min_wait_time = u64::MAX;
        let mut d_ref: Option<DeploymentEntry<Tag::Model>> = None;

        let g = self.get_group(group.clone())?;
        let group_size = g.value().len();
        debug!("Routing group `{group}` ({group_size} deployments)");

        for d in g.value() {
            let wait_time = d.min_cooldown_time(token_count).await;
            trace!("  `{}` cooldown: {wait_time}ms", d.identifier());
            if wait_time == 0 {
                debug!("  Selected `{}` (immediately available)", d.identifier());
                d_ref = Some(d.clone());
                break;
            } else if wait_time < min_wait_time {
                min_wait_time = wait_time;
                d_ref = Some(d.clone());
            }
        }

        if let Some(d) = &d_ref
            && min_wait_time != u64::MAX
        {
            debug!(
                "  Selected `{}` (least wait: {min_wait_time}ms)",
                d.identifier()
            );
        }

        d_ref.ok_or_else(|| {
            ThrydError::Router(format!("No deployment available for group `{}`", group))
        })
    }

    /// Create a deployment for a model from a provider.
    ///
    /// # Arguments
    /// * `identifier` - Deployment identifier string
    /// * `rpm` - Optional RPM quota
    /// * `tpm` - Optional TPM quota
    fn create_deployment(
        &self,
        identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> Result<Deployment<Tag::Model>> {
        let (provider_name, model_name) = analyze_identifier(identifier)?;
        debug!("Creating deployment for `{model_name}` of `{provider_name}`");
        Ok(Deployment::new(Tag::create_model(
            self.get_provider(provider_name)?,
            model_name,
        )?)
        .with_usage_constrain(rpm, tpm))
    }

    /// Get a provider by name.
    pub fn get_provider(&self, provider_name: ProviderName) -> Result<Arc<dyn Provider>> {
        self.providers
            .get(provider_name.as_str())
            .ok_or_else(|| {
                ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
            })
            .map(|p| p.value().clone())
    }

    /// Invoke a request bypassing the cache read.
    /// Always calls the LLM directly and writes the result back to cache,
    /// overriding any stale entry so future cached calls get the fresh response.
    pub async fn invoke_fresh(
        &self,
        send_to: RouteGroupName,
        request: Tag::Request,
    ) -> Result<Tag::Response> {
        debug!("Invoke (no-cache read) → group `{send_to}`");
        let d = self
            .wait_for_any(send_to, Tag::cont_tokens(&request))
            .await?;
        debug!("Executing request on `{}`", d.identifier());
        let key = Tag::cache_key(&request);
        let rc = self.retry.read().unwrap().clone();
        let res = if let Some(rc) = rc {
            let d2 = d.clone();
            let r2 = request.clone();
            retry_on_transient(&rc, || Tag::execute_request(d2.clone(), r2.clone())).await?
        } else {
            Tag::execute_request(d.clone(), request).await?
        };
        d.record_usage(Tag::total_response_tokens(&res)).await;
        if let Some(cache) = &self.cache {
            debug!("Overriding cache for: {key}");
            match &key {
                CacheKey::Single(k) => {
                    cache.set_ser(k.as_str(), &res)?;
                }
                CacheKey::Batch(ks) => {
                    let vals = Tag::breakdown_batch_response(res.clone());
                    for (k, val) in ks.iter().zip(vals) {
                        cache.set_ser(k.as_str(), &val)?;
                    }
                }
            }
        }
        Ok(res)
    }
}

impl<Tag: ModelTypeTag + Send> Router<Tag> {
    pub async fn invoke(
        &self,
        send_to: RouteGroupName,
        request: Tag::Request,
        no_cache: bool,
    ) -> Result<Tag::Response> {
        debug!("Invoke dispatch: group=`{send_to}`, no_cache={no_cache}");
        if no_cache {
            self.invoke_fresh(send_to, request).await
        } else {
            self.invoke_cached(send_to, request).await
        }
    }

    pub async fn invoke_cached(
        &self,
        send_to: RouteGroupName,
        request: Tag::Request,
    ) -> Result<Tag::Response> {
        debug!("Invoke (cached) → group `{send_to}`");
        let d = self
            .wait_for_any(send_to, Tag::cont_tokens(&request))
            .await?;
        debug!("Resolving cache for `{}`", d.identifier());
        let rc = self.retry.read().unwrap().clone();
        let res = if let Some(rc) = rc {
            let cache = &self.cache;
            let d2 = d.clone();
            let r2 = request.clone();
            retry_on_transient(&rc, || Tag::cache_resolve(cache, d2.clone(), r2.clone())).await
        } else {
            Tag::cache_resolve(&self.cache, d.clone(), request).await
        };
        if let Ok(r) = res.as_ref() {
            d.record_usage(Tag::total_response_tokens(r)).await;
        }
        res
    }
}

impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            providers: DashMap::default(),
            groups: DashMap::default(),
            retry: std::sync::RwLock::new(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::deployment::Deployment;
    use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest};
    use crate::models::dummy::DummyModel;
    use crate::provider::dummy::DummyProvider;
    use crate::{RankingResponse, RerankerModel, RerankerRequest, Usage};

    #[tokio::test]
    async fn test_router_reranker_with_dummy() {
        let router = Router::<RerankerTag>::default();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        let model = DummyModel::new("reranker".to_string(), provider)
            .with_reranker_responses(vec![vec![(0, 0.95), (2, 0.87), (1, 0.72)]]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn RerankerModel>);
        router.add_deployment("rank".into(), deployment).unwrap();

        let request = RerankerRequest {
            query: "What is Rust?".to_string(),
            documents: vec![
                "Rust is a systems language".to_string(),
                "Python is scripting".to_string(),
                "Rust memory safety".to_string(),
            ],
        };

        let result = router.invoke_cached("rank".into(), request).await.unwrap();

        assert_eq!(result.rankings, vec![(0, 0.95), (2, 0.87), (1, 0.72)]);
    }

    #[tokio::test]
    async fn test_router_reranker_cache_hit() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("reranker-cache.db");

        let router = Router::<RerankerTag>::with_cache(&db_path).unwrap();
        // Verify PersistentCache can store and retrieve a Ranking
        {
            let cache = router.cache.as_ref().unwrap();
            let test_ranking = RankingResponse {
                rankings: vec![(0, 0.95), (1, 0.8)],
                usage: Usage::default(),
            };
            cache.set_ser("ranking_test", &test_ranking).unwrap();
            let retrieved: Option<RankingResponse> = cache.get_de("ranking_test");
            assert_eq!(
                retrieved,
                Some(test_ranking),
                "PersistentCache roundtrip failed"
            );
        }

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Configure only one response — cache must serve it on the second call
        let model = DummyModel::new("reranker".to_string(), provider)
            .with_reranker_responses(vec![vec![(0, 0.9)]]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn RerankerModel>);
        router.add_deployment("rank".into(), deployment).unwrap();

        let request = RerankerRequest {
            query: "q".to_string(),
            documents: vec!["doc_a".to_string(), "doc_b".to_string()],
        };

        // First call hits the model and caches the result
        let first = router
            .invoke_cached("rank".into(), request.clone())
            .await
            .unwrap();
        assert_eq!(first.rankings, vec![(0, 0.9)]);

        // Second call must return cached result (only 1 response was configured)
        let second = router.invoke_cached("rank".into(), request).await.unwrap();
        assert_eq!(first, second);
    }

    #[tokio::test]
    async fn test_embedding_sparse_cache_per_text() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("emb-cache.db");
        let router = Router::<EmbeddingTag>::with_cache(&db_path).unwrap();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Single response: first API call returns 2 embeddings for ["A", "B"]
        let model = DummyModel::new("embed".to_string(), provider)
            .with_embedding_responses(vec![vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]]]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn EmbeddingModel>);
        router.add_deployment("embed".into(), deployment).unwrap();

        // First call: uncached ["A", "B"] → hits API
        let first = router
            .invoke_cached(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["hello".into(), "world".into()],
                    ndim: 3,
                },
            )
            .await
            .unwrap();
        assert_eq!(
            first.embeddings,
            vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]]
        );

        // Second call: ["hello"] → cache hit, no API call (only 1 response configured)
        let second = router
            .invoke_cached(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["hello".into()],
                    ndim: 3,
                },
            )
            .await
            .unwrap();
        assert_eq!(second.embeddings, vec![vec![0.1, 0.2, 0.3]]);
    }

    #[tokio::test]
    async fn test_embedding_sparse_cache_within_batch_dedup() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("dedup-cache.db");
        let router = Router::<EmbeddingTag>::with_cache(&db_path).unwrap();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Two responses: API called for ["hello", "hello"] (no dedup)
        let model = DummyModel::new("embed".to_string(), provider)
            .with_embedding_responses(vec![vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]]]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn EmbeddingModel>);
        router.add_deployment("embed".into(), deployment).unwrap();

        // Request with duplicate text: ["hello", "hello"] → API called for both
        let result = router
            .invoke_cached(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["hello".into(), "hello".into()],
                    ndim: 3,
                },
            )
            .await
            .unwrap();

        // Returns two embeddings (no dedup — both hit the API)
        assert_eq!(result.embeddings.len(), 2);
        assert_eq!(result.embeddings[0], vec![0.1, 0.2, 0.3]);
        assert_eq!(result.embeddings[1], vec![0.4, 0.5, 0.6]);
    }

    #[tokio::test]
    async fn test_embedding_sparse_cache_mixed() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("mixed-cache.db");
        let router = Router::<EmbeddingTag>::with_cache(&db_path).unwrap();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Two responses: DummyModel pops LIFO, so last element is returned first
        // Index 1 (last): first call → ["A", "B"] → 2 embeddings
        // Index 0 (first): second call → ["C"] → 1 embedding
        let model = DummyModel::new("embed".to_string(), provider).with_embedding_responses(vec![
            vec![vec![0.7, 0.8, 0.9]],
            vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]],
        ]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn EmbeddingModel>);
        router.add_deployment("embed".into(), deployment).unwrap();

        // First call: ["A", "B"] → API call, both cached
        let first = router
            .invoke_cached(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["A".into(), "B".into()],
                    ndim: 3,
                },
            )
            .await
            .unwrap();
        assert_eq!(
            first.embeddings,
            vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]]
        );

        // Second call: ["A", "C"] → "A" cached, "C" uncached → only API call for "C"
        let second = router
            .invoke_cached(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["A".into(), "C".into()],
                    ndim: 3,
                },
            )
            .await
            .unwrap();
        assert_eq!(
            second.embeddings,
            vec![vec![0.1, 0.2, 0.3], vec![0.7, 0.8, 0.9]]
        );
    }

    #[tokio::test]
    async fn test_embedding_sparse_cache_no_cache_bypass() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("nocache-cache.db");
        let router = Router::<EmbeddingTag>::with_cache(&db_path).unwrap();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Two responses: DummyModel pops LIFO, so last element is returned first
        let model = DummyModel::new("embed".to_string(), provider)
            .with_embedding_responses(vec![vec![vec![0.7, 0.8, 0.9]], vec![vec![0.1, 0.2, 0.3]]]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn EmbeddingModel>);
        router.add_deployment("embed".into(), deployment).unwrap();

        // First call with no_cache=true → bypasses cache, calls API
        let first = router
            .invoke(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["hello".into()],
                    ndim: 3,
                },
                true,
            )
            .await
            .unwrap();
        assert_eq!(first.embeddings, vec![vec![0.1, 0.2, 0.3]]);

        // Second call with no_cache=false → cache HIT (invoke_fresh wrote to cache)
        let second = router
            .invoke(
                "embed".into(),
                EmbeddingRequest {
                    texts: vec!["hello".into()],
                    ndim: 3,
                },
                false,
            )
            .await
            .unwrap();
        assert_eq!(second.embeddings, vec![vec![0.1, 0.2, 0.3]]);
    }

    #[tokio::test]
    async fn test_retry_succeeds_first_try() {
        let config = RetryConfig {
            max_retries: 3,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let result = retry_on_transient(&config, || async { Ok::<_, ThrydError>(42) }).await;
        assert_eq!(result.unwrap(), 42);
    }

    #[tokio::test]
    async fn test_retry_succeeds_after_transient_failures() {
        let config = RetryConfig {
            max_retries: 3,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let attempts = std::sync::atomic::AtomicU32::new(0);
        let result = retry_on_transient(&config, || {
            let n = attempts.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            async move {
                if n < 2 {
                    Err(ThrydError::Timeout(5000))
                } else {
                    Ok("success")
                }
            }
        })
        .await;
        assert_eq!(result.unwrap(), "success");
        assert_eq!(attempts.load(std::sync::atomic::Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn test_retry_fails_on_non_transient_error() {
        let config = RetryConfig {
            max_retries: 3,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let attempts = std::sync::atomic::AtomicU32::new(0);
        let result: std::result::Result<(), _> = retry_on_transient(&config, || {
            attempts.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            async { Err(ThrydError::Router("bad group".into())) }
        })
        .await;
        assert!(result.is_err());
        // Non-transient error → fail immediately, no retry
        assert_eq!(attempts.load(std::sync::atomic::Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn test_retry_exhausted_returns_last_error() {
        let config = RetryConfig {
            max_retries: 2,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let attempts = std::sync::atomic::AtomicU32::new(0);
        let result: std::result::Result<(), _> = retry_on_transient(&config, || {
            attempts.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            async { Err(ThrydError::Timeout(1000)) }
        })
        .await;
        assert!(result.is_err());
        // 1 initial + 2 retries = 3 total attempts
        assert_eq!(attempts.load(std::sync::atomic::Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn test_retry_respects_rate_limit_wait_time() {
        let config = RetryConfig {
            max_retries: 1,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let start = std::time::Instant::now();
        let result: std::result::Result<(), _> = retry_on_transient(&config, || async {
            Err(ThrydError::RateLimitExceeded { wait_time_ms: 50 })
        })
        .await;
        assert!(result.is_err());
        // Should have waited at least 50ms (the rate limit floor), not just 1ms (initial backoff)
        assert!(start.elapsed() >= std::time::Duration::from_millis(45));
    }

    #[tokio::test]
    async fn test_retry_api_error_5xx_is_transient() {
        let config = RetryConfig {
            max_retries: 1,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let attempts = std::sync::atomic::AtomicU32::new(0);
        let result = retry_on_transient(&config, || {
            let n = attempts.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            async move {
                if n == 0 {
                    Err(ThrydError::ApiError {
                        status: 503,
                        body: "Service Unavailable".into(),
                    })
                } else {
                    Ok("recovered")
                }
            }
        })
        .await;
        assert_eq!(result.unwrap(), "recovered");
        assert_eq!(attempts.load(std::sync::atomic::Ordering::SeqCst), 2);
    }

    #[tokio::test]
    async fn test_retry_api_error_400_is_not_transient() {
        let config = RetryConfig {
            max_retries: 3,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        };
        let attempts = std::sync::atomic::AtomicU32::new(0);
        let result: std::result::Result<(), _> = retry_on_transient(&config, || {
            attempts.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            async {
                Err(ThrydError::ApiError {
                    status: 400,
                    body: "Bad Request".into(),
                })
            }
        })
        .await;
        assert!(result.is_err());
        // 400 is not transient → fail immediately
        assert_eq!(attempts.load(std::sync::atomic::Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn test_retry_integration_invoke_fresh_with_transient_errors() {
        let router = Router::<CompletionTag>::default().with_retry(RetryConfig {
            max_retries: 2,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        });

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // LIFO: errors popped first (last-in first-out)
        // Queue: [timeout_err, timeout_err, "ok"] → "ok" is popped last (first call), errors first
        // Actually LIFO means last element returned first.
        // We want: call 1 → timeout, call 2 → timeout, call 3 → "ok"
        // So push: ["ok", timeout, timeout] → pop order: timeout, timeout, "ok"
        let model = DummyModel::new("retry-test".to_string(), provider)
            .with_completion_errors(vec![ThrydError::Timeout(1000), ThrydError::Timeout(1000)])
            .with_completion_responses(vec!["recovered".to_string()]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn CompletionModel>);
        router.add_deployment("test".into(), deployment).unwrap();

        let result = router
            .invoke_fresh(
                "test".into(),
                CompletionRequest {
                    message: "hello".into(),
                    ..Default::default()
                },
            )
            .await
            .unwrap();

        assert_eq!(result.content, "recovered");
    }

    #[tokio::test]
    async fn test_retry_integration_invoke_cached_with_transient_errors() {
        let router = Router::<CompletionTag>::default().with_retry(RetryConfig {
            max_retries: 2,
            initial_backoff_ms: 1,
            max_backoff_ms: 10,
            backoff_multiplier: 2.0,
        });

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        let model = DummyModel::new("retry-cached-test".to_string(), provider)
            .with_completion_errors(vec![ThrydError::ApiError {
                status: 503,
                body: "Service Unavailable".into(),
            }])
            .with_completion_responses(vec!["ok".to_string()]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn CompletionModel>);
        router.add_deployment("test".into(), deployment).unwrap();

        let result = router
            .invoke_cached(
                "test".into(),
                CompletionRequest {
                    message: "hello".into(),
                    ..Default::default()
                },
            )
            .await
            .unwrap();

        assert_eq!(result.content, "ok");
    }

    #[tokio::test]
    async fn test_retry_integration_disabled_by_default() {
        // Router without retry → transient errors propagate immediately
        let router = Router::<CompletionTag>::default();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        let model = DummyModel::new("no-retry".to_string(), provider)
            .with_completion_errors(vec![ThrydError::Timeout(1000)])
            .with_completion_responses(vec!["ok".to_string()]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn CompletionModel>);
        router.add_deployment("test".into(), deployment).unwrap();

        let result = router
            .invoke_fresh(
                "test".into(),
                CompletionRequest {
                    message: "hello".into(),
                    ..Default::default()
                },
            )
            .await;

        // Should fail immediately — no retry configured
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), ThrydError::Timeout(1000)));
    }
}
