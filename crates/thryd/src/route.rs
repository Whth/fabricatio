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

use crate::Result;
use crate::deployment::Deployment;
use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use crate::tracker::Quota;
use crate::utils::analyze_identifier;
use crate::{
    Completion, Embedding, Embeddings, PersistentCache, Ranking, RerankerModel, RerankerRequest,
    ThrydError,
};
use async_trait::async_trait;
use dashmap::DashMap;
use dashmap::mapref::one::Ref;
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::path::Path;
use std::sync::Arc;
use tracing::*;

/// Configuration for automatic retry on transient network failures.
///
/// When configured on a [`Router`], failed requests will be retried with
/// exponential backoff for errors classified as transient (network failures,
/// timeouts, upstream 429/5xx).
///
/// # Example
///
/// ```ignore
/// use thryd::{Router, CompletionTag, RetryConfig};
///
/// let router = Router::<CompletionTag>::default()
///     .with_retry(RetryConfig {
///         max_retries: 3,
///         initial_backoff_ms: 500,
///         ..RetryConfig::default()
///     });
/// ```
#[derive(Debug, Clone)]
pub struct RetryConfig {
    /// Maximum number of retry attempts after the initial failure. `0` means no retries.
    pub max_retries: u32,
    /// Initial backoff duration in milliseconds before the first retry.
    pub initial_backoff_ms: u64,
    /// Cap on backoff duration in milliseconds.
    pub max_backoff_ms: u64,
    /// Multiplier applied to backoff after each retry (exponential backoff).
    pub backoff_multiplier: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            initial_backoff_ms: 1000,
            max_backoff_ms: 30_000,
            backoff_multiplier: 2.0,
        }
    }
}

/// Execute an async operation with retry on transient errors.
///
/// Retries on network failures, timeouts, and upstream 429/5xx errors.
/// Uses exponential backoff, respecting `RateLimitExceeded.wait_time_ms` as floor.
async fn retry_on_transient<F, Fut, T>(config: &RetryConfig, mut op: F) -> Result<T>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<T>>,
{
    let mut attempt = 0u32;
    loop {
        match op().await {
            Ok(val) => return Ok(val),
            Err(e) if attempt < config.max_retries && is_transient(&e) => {
                attempt += 1;
                let base = (config.initial_backoff_ms as f64
                    * config.backoff_multiplier.powi(attempt as i32 - 1))
                .min(config.max_backoff_ms as f64) as u64;

                let wait_ms = match &e {
                    ThrydError::RateLimitExceeded { wait_time_ms } => base.max(*wait_time_ms),
                    _ => base,
                };

                warn!(
                    "Transient error (attempt {}/{}): {}. Retrying in {}ms",
                    attempt, config.max_retries, e, wait_ms
                );
                tokio::time::sleep(tokio::time::Duration::from_millis(wait_ms)).await;
            }
            Err(e) => return Err(e),
        }
    }
}

/// Returns `true` for errors caused by transient network/server conditions.
fn is_transient(e: &ThrydError) -> bool {
    match e {
        ThrydError::Reqwest(_)
        | ThrydError::Timeout(_)
        | ThrydError::RateLimitExceeded { .. }
        | ThrydError::SSE(_) => true,
        ThrydError::ApiError { status, .. } => *status == 429 || *status >= 500,
        _ => false,
    }
}

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
    /// * `input_text` - Input text for token counting (affects TPM calculation)
    ///
    /// # Returns
    /// * `Ok(DeploymentEntry)` - The selected deployment
    /// * `Err(ThrydError::Router)` - If no deployments exist in the group
    async fn wait_for_any(
        &self,
        group: RouteGroupName,
        input_text: String,
    ) -> Result<DeploymentEntry<Tag::Model>> {
        let mut min_wait_time = u64::MAX;
        let mut d_ref: Option<DeploymentEntry<Tag::Model>> = None;

        let g = self.get_group(group.clone())?;
        let group_size = g.value().len();
        debug!("Routing group `{group}` ({group_size} deployments)");

        for d in g.value() {
            let wait_time = d.min_cooldown_time(input_text.clone()).await;
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

    /// Invoke a model in the specified group.
    ///
    /// This is the main entry point for making requests. The routing logic:
    ///
    /// 1. **Wait for availability**: Find the least-loaded deployment using cooldown times
    /// 2. **Cache check**: If caching enabled, check for existing result by content hash
    /// 3. **Execute**: Call the deployment's model method if no cache hit
    /// 4. **Cache result**: Store the response if caching enabled
    ///
    /// # Arguments
    /// * `send_to` - The group name to route the request to
    /// * `request` - The request payload (type depends on `Tag`)
    ///
    /// # Returns
    /// * `Ok(Tag::Response)` - The model response (cached or freshly generated)
    /// * `Err(ThrydError::Router)` - If no deployments available in the group
    /// * `Err(ThrydError::Cache)` - If cache read/write fails
    /// * `Err(ThrydError::Provider)` - If the model call fails
    ///
    /// # Routing Strategy
    ///
    /// Requests are routed to the deployment with:
    /// - Zero cooldown time if any deployment is immediately available
    /// - Otherwise, the deployment with the shortest projected wait time
    ///
    /// This achieves load balancing across multiple deployments.
    ///
    /// # Example: Completion
    ///
    /// ```rust
    ///
    ///
    /// let response = router.invoke("chat".into(), CompletionRequest {
    ///     message: "What is the meaning of life?".into(),
    ///     stream: false,
    ///     top_p: Some(0.9),
    ///     temperature: Some(0.7),
    ///     max_completion_tokens: Some(500),
    ///     presence_penalty: None,
    ///     frequency_penalty: None,
    /// }).await?;
    /// ```
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
            .wait_for_any(send_to, Tag::prepare_input_text(&request))
            .await?;
        debug!("Executing request on `{}`", d.identifier());
        let key = Tag::prepare_cache_key(&request);
        let rc = self.retry.read().unwrap().clone();
        let res = if let Some(rc) = rc {
            let d2 = d.clone();
            let r2 = request.clone();
            retry_on_transient(&rc, || Tag::execute_request(d2.clone(), r2.clone())).await?
        } else {
            Tag::execute_request(d, request).await?
        };
        if let Some(cache) = &self.cache {
            debug!("Overriding cache for: {key}");
            cache.set_ser(&key, &res)?;
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
            .wait_for_any(send_to, Tag::prepare_input_text(&request))
            .await?;
        debug!("Resolving cache for `{}`", d.identifier());
        let rc = self.retry.read().unwrap().clone();
        if let Some(rc) = rc {
            let cache = &self.cache;
            let d2 = d.clone();
            let r2 = request.clone();
            retry_on_transient(&rc, || Tag::cache_resolve(cache, d2.clone(), r2.clone())).await
        } else {
            Tag::cache_resolve(&self.cache, d, request).await
        }
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

/// Trait defining type-level routing behavior for different model types.
///
/// This trait implements the **type-level tag pattern**, using Rust's type system
/// to route requests to the correct model type and handle serialization/caching.
///
/// # Type Parameters
///
/// * `Model` - The underlying model type (e.g., `dyn CompletionModel`)
/// * `Request` - The request struct for this model type
/// * `Response` - The response type for this model type
///
/// # Implementing ModelTypeTag
///
/// Implementors must define:
/// - `create_model`: How to instantiate a model from a provider and name
/// - `prepare_input_text`: How to extract text from requests (for cache keys, TPM counting)
/// - `execute_request`: How to call the model with a request
///
/// # Example: Implementing for a Custom Model Type
///
/// ```ignore
/// use async_trait::async_trait;
/// use thryd::{Result, ThrydError, router::{ModelTypeTag, DeploymentEntry}};
/// use thryd::model::{Model, MyCustomRequest, MyCustomResponse};
/// use thryd::provider::Provider;
/// use std::sync::Arc;
///
/// struct MyCustomTag;
///
/// #[async_trait]
/// impl ModelTypeTag for MyCustomTag {
///     type Model = dyn MyCustomModel;
///     type Request = MyCustomRequest;
///     type Response = MyCustomResponse;
///
///     fn create_model(provider: Arc<dyn Provider>, model_name: String) -> Result<Box<Self::Model>> {
///         provider.create_custom_model(model_name)
///     }
///
///     fn prepare_input_text(request: &Self::Request) -> String {
///         request.input.clone()
///     }
///
///     async fn execute_request(
///         deployment: Arc<Deployment<Self::Model>>,
///         request: Self::Request,
///     ) -> Result<Self::Response> {
///         deployment.custom_inference(request).await
///     }
/// }
/// ```
#[async_trait]
pub trait ModelTypeTag {
    /// The underlying model type for this tag.
    type Model: ?Sized + Model;

    /// The request struct type for this model type.
    /// Must be `Send + Clone` to support async_trait default method futures and retry.
    type Request: Send + Clone;

    /// The response type for this model type.
    /// Must support serialization for caching and deserialization for cache retrieval.
    type Response: DeserializeOwned + Serialize + Clone;

    /// Create a model instance from a provider and model name.
    ///
    /// # Arguments
    /// * `provider` - The provider to create the model from
    /// * `model_name` - The name of the model within the provider
    ///
    /// # Returns
    /// * `Ok(Box<Self::Model>)` - The created model
    /// * `Err(ThrydError::Provider)` - If creation fails
    fn create_model(provider: Arc<dyn Provider>, model_name: ModelName)
    -> Result<Box<Self::Model>>;

    /// Extract text from a request for rate limit calculations.
    ///
    /// The returned string is used for:
    /// - Token counting (TPM quota tracking)
    /// - Cache key generation (via `prepare_cache_key`)
    ///
    /// # Arguments
    /// * `request` - The request to extract text from
    fn prepare_input_text(request: &Self::Request) -> String;

    /// Generate a cache key for a request.
    ///
    /// Default implementation hashes `prepare_input_text(request)` with blake3.
    /// Override to customize cache key generation.
    fn prepare_cache_key(request: &Self::Request) -> String {
        blake3::hash(Self::prepare_input_text(request).as_bytes()).to_string()
    }

    /// Each tag defines its own caching strategy. Default: batch-level.
    /// Override for per-item sparse caching.
    async fn cache_resolve(
        cache: &Option<PersistentCache>,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        if let Some(cache) = cache {
            let key = Self::prepare_cache_key(&request);
            if let Some(val) = cache.get_de::<Self::Response>(key.as_str()) {
                debug!("Cache hit for: {key}");
                Ok(val)
            } else {
                debug!("Cache missed for: {key}");
                // Split creation from await so request is consumed before the await point,
                // satisfying async_trait Send requirement on the default implementation.
                let fut = Self::execute_request(deployment, request);
                let res = fut.await?;
                debug!("Caching result for: {key}");
                cache.set_ser(&key, &res)?;
                Ok(res)
            }
        } else {
            let fut = Self::execute_request(deployment, request);
            fut.await
        }
    }

    /// Execute a request against a deployment.
    ///
    /// # Arguments
    /// * `deployment` - The deployment to call
    /// * `request` - The request to execute
    ///
    /// # Returns
    /// * `Ok(Self::Response)` - The model response
    /// * `Err(ThrydError::Provider)` - If the model call fails
    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response>;
}

/// Tag type for completion/chat models.
///
/// Use with [`Router<CompletionTag>`] for text generation requests.
///
/// # Example
///
/// ```ignore
/// let mut router = Router::<CompletionTag>::default();
/// router.add_provider(openai)?;
///
/// router.deploy("chat", "openai/gpt-4".into(), Some(60), Some(100_000))?;
///
/// let response = router.invoke("chat".into(), CompletionRequest {
///     message: "Hello!".into(),
///     stream: false,
///     top_p: None, temperature: None,
///     max_completion_tokens: Some(100),
///     presence_penalty: None, frequency_penalty: None,
/// }).await?;
/// ```
#[derive(Default)]
pub struct CompletionTag;

/// Tag type for embedding models.
///
/// Use with [`Router<EmbeddingTag>`] for text embedding requests.
///
/// # Example
///
/// ```ignore
/// let mut router = Router::<EmbeddingTag>::default();
/// router.add_provider(openai)?;
///
/// router.deploy("embed", "openai/text-embedding-3-small".into(), Some(3000), None)?;
///
/// let embeddings = router.invoke("embed".into(), EmbeddingRequest {
///     texts: vec!["hello world".into()],
/// }).await?;
/// ```
#[derive(Default)]
pub struct EmbeddingTag;

/// Tag type for reranker models.
///
/// Use with [`Router<RerankerTag>`] for document reranking requests.
///
/// # Example
///
/// ```ignore
/// let mut router = Router::<RerankerTag>::default();
/// router.add_provider(cohere)?;
///
/// router.deploy("rank", "cohere/rerank-3".into(), Some(100), None)?;
///
/// let rankings = router.invoke("rank".into(), RerankerRequest {
///     query: "What is Rust?".into(),
///     documents: vec![
///         "Rust is a programming language".into(),
///         "Python is great".into(),
///     ],
/// }).await?;
/// // Returns: [(0, 0.95), (1, 0.30)] - document indices sorted by score
/// ```
#[derive(Default)]
pub struct RerankerTag;

#[async_trait]
impl ModelTypeTag for RerankerTag {
    type Model = dyn RerankerModel;
    type Request = RerankerRequest;
    type Response = Ranking;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_reranker_model(model_name)
    }

    fn prepare_input_text(request: &Self::Request) -> String {
        let mut t_seq = request.documents.clone();
        t_seq.sort();
        t_seq.concat()
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.rerank(request).await
    }
}

#[async_trait]
impl ModelTypeTag for CompletionTag {
    type Model = dyn CompletionModel;
    type Request = CompletionRequest;
    type Response = Completion;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_completion_model(model_name)
    }

    fn prepare_input_text(request: &Self::Request) -> String {
        request.message.to_string()
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.completion(request).await
    }
}

#[async_trait]
impl ModelTypeTag for EmbeddingTag {
    type Model = dyn EmbeddingModel;
    type Request = EmbeddingRequest;
    type Response = Embeddings;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_embedding_model(model_name)
    }

    fn prepare_input_text(request: &Self::Request) -> String {
        let mut t_seq = request.texts.clone();
        t_seq.sort();
        t_seq.concat()
    }

    async fn cache_resolve(
        cache: &Option<PersistentCache>,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        // Fast path: no cache → execute directly (moves request, no partial destructure)
        let cache = match cache {
            Some(c) => c,
            None => {
                // Split creation from await to satisfy async_trait Send requirement
                let fut = Self::execute_request(deployment, request);
                return fut.await;
            }
        };

        let ndim = request.ndim;
        let total = request.texts.len();
        let texts = request.texts;

        // Phase 1: Check cache for each unique text
        // text_status maps text → Some(embedding) if cached, None if uncached
        let mut text_status: std::collections::HashMap<String, Option<Embedding>> =
            std::collections::HashMap::with_capacity(texts.len());
        let mut all_cached = true;

        for text in &texts {
            if text_status.contains_key(text) {
                continue;
            }
            let key = format!("emb:{}:{}", ndim, blake3::hash(text.as_bytes()));
            if let Some(emb) = cache.get_de::<Embedding>(&key) {
                text_status.insert(text.clone(), Some(emb));
            } else {
                text_status.insert(text.clone(), None);
                all_cached = false;
            }
        }

        let unique = text_status.len();
        let cached_count = text_status.values().filter(|v| v.is_some()).count();
        let uncached_count = unique - cached_count;
        debug!(
            "Embedding cache: {total} texts, {unique} unique, {cached_count} cached, {uncached_count} uncached (ndim={ndim})"
        );

        // Phase 2: All cached → return immediately
        if all_cached {
            debug!("All {unique} unique texts cache-hit, returning immediately");
            return Ok(texts
                .iter()
                .map(|t| text_status.get(t).unwrap().clone().unwrap())
                .collect());
        }

        // Phase 3: Collect unique uncached texts in original order (first occurrence)
        let mut uncached: Vec<String> = Vec::new();
        let mut seen = std::collections::HashSet::new();
        for text in &texts {
            if text_status.get(text).unwrap().is_none() && seen.insert(text.clone()) {
                uncached.push(text.clone());
            }
        }

        // Phase 4: Call API once for all uncached texts
        let uncached_len = uncached.len();
        debug!("Embedding API call: {uncached_len} uncached texts");
        let sub_request = EmbeddingRequest {
            texts: uncached.clone(),
            ndim,
        };
        // Split creation from await to satisfy async_trait Send requirement
        let fut = Self::execute_request(deployment, sub_request);
        let fresh = fut.await?;

        // Phase 5: Store each fresh embedding in cache
        for (text, emb) in uncached.iter().zip(fresh) {
            let key = format!("emb:{}:{}", ndim, blake3::hash(text.as_bytes()));
            cache.set_ser(&key, &emb)?;
            text_status.insert(text.clone(), Some(emb));
        }
        debug!("Cached {uncached_len} fresh embeddings");

        // Phase 6: Assemble final result preserving original order & duplicates
        Ok(texts
            .into_iter()
            .map(|t| text_status.get(&t).unwrap().clone().unwrap())
            .collect())
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.embedding(request).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::deployment::Deployment;
    use crate::models::dummy::DummyModel;
    use crate::provider::dummy::DummyProvider;

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

        assert_eq!(result, vec![(0, 0.95), (2, 0.87), (1, 0.72)]);
    }

    #[tokio::test]
    async fn test_router_reranker_cache_hit() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("reranker-cache.db");

        let router = Router::<RerankerTag>::with_cache(&db_path).unwrap();
        // Verify PersistentCache can store and retrieve a Ranking
        {
            let cache = router.cache.as_ref().unwrap();
            let test_ranking: Ranking = vec![(0, 0.95), (1, 0.8)];
            cache.set_ser("ranking_test", &test_ranking).unwrap();
            let retrieved: Option<Ranking> = cache.get_de("ranking_test");
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
        assert_eq!(first, vec![(0, 0.9)]);

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
        assert_eq!(first, vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]]);

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
        assert_eq!(second, vec![vec![0.1, 0.2, 0.3]]);
    }

    #[tokio::test]
    async fn test_embedding_sparse_cache_within_batch_dedup() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("dedup-cache.db");
        let router = Router::<EmbeddingTag>::with_cache(&db_path).unwrap();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Single response: one embedding for deduped ["hello"]
        let model = DummyModel::new("embed".to_string(), provider)
            .with_embedding_responses(vec![vec![vec![0.1, 0.2, 0.3]]]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn EmbeddingModel>);
        router.add_deployment("embed".into(), deployment).unwrap();

        // Request with duplicate text: ["hello", "hello"] → API called once for ["hello"]
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

        // Should return two copies of the same embedding
        assert_eq!(result.len(), 2);
        assert_eq!(result[0], vec![0.1, 0.2, 0.3]);
        assert_eq!(result[1], vec![0.1, 0.2, 0.3]);
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
        assert_eq!(first, vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]]);

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
        assert_eq!(second, vec![vec![0.1, 0.2, 0.3], vec![0.7, 0.8, 0.9]]);
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

        // First call with no_cache=true → bypasses cache entirely, calls API
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
        assert_eq!(first, vec![vec![0.1, 0.2, 0.3]]);

        // Second call with no_cache=false → cache miss (fresh call didn't write) → API call
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
        assert_eq!(second, vec![vec![0.7, 0.8, 0.9]]);
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

        assert_eq!(result, "recovered");
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

        assert_eq!(result, "ok");
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
