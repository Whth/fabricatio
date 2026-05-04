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
    Completion, DEFAULT_MAX_CAPACITY, DEFAULT_TTL_SECS, Embeddings, Ranking, RerankerModel,
    RerankerRequest, ThrydError, TieredCache,
};
use async_trait::async_trait;
use dashmap::DashMap;
use dashmap::mapref::one::Ref;
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::path::Path;
use std::sync::Arc;
use tracing::*;

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
    cache: Option<TieredCache>,

    /// Registered providers by name. Thread-safe concurrent map.
    providers: DashMap<ProviderName, Arc<dyn Provider>>,

    /// Deployment groups by name. Each group contains deployments for routing.
    groups: DashMap<RouteGroupName, Vec<DeploymentEntry<Tag::Model>>>,
}

impl<Tag: ModelTypeTag> Router<Tag> {
    /// Create a router with persistent caching enabled.
    ///
    /// # Arguments
    /// * `database_file` - Path to the SQLite cache database file.
    ///   Created automatically if it doesn't exist.
    ///
    /// # Returns
    /// A new `Router` instance with caching initialized.
    ///
    /// # Example
    ///
    /// ```ignore
    /// let router = Router::<CompletionTag>::with_cache("./llm-cache.db")?;
    /// ```
    pub fn with_cache(database_file: impl AsRef<Path>) -> Result<Self> {
        Ok(Self {
            cache: Some(TieredCache::create_or_open(
                database_file,
                DEFAULT_TTL_SECS,
                DEFAULT_MAX_CAPACITY,
            )?),
            ..Self::default()
        })
    }

    /// Create a router with custom cache TTL and capacity.
    pub fn with_cache_config(
        database_file: impl AsRef<Path>,
        ttl_secs: u64,
        max_capacity: u64,
    ) -> Result<Self> {
        Ok(Self {
            cache: Some(TieredCache::create_or_open(
                database_file,
                ttl_secs,
                max_capacity,
            )?),
            ..Self::default()
        })
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

        for d in g.value() {
            let wait_time = d.min_cooldown_time(input_text.clone()).await;
            if wait_time == 0 {
                d_ref = Some(d.clone());
                break;
            } else if wait_time < min_wait_time {
                min_wait_time = wait_time;
                d_ref = Some(d.clone());
            }
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
    /// Invoke a request bypassing all cache layers.
    /// Always calls the LLM directly and never writes to cache.
    pub async fn invoke_fresh(
        &self,
        send_to: RouteGroupName,
        request: Tag::Request,
    ) -> Result<Tag::Response> {
        debug!("Invoking route (no cache): {}", send_to);
        let d = self
            .wait_for_any(send_to, Tag::prepare_input_text(&request))
            .await?;
        Tag::execute_request(d, request).await
    }

    pub async fn invoke(
        &self,
        send_to: RouteGroupName,
        request: Tag::Request,
        no_cache: bool,
    ) -> Result<Tag::Response> {
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
        debug!("Invoking route (cached): {}", send_to);

        let d = self
            .wait_for_any(send_to, Tag::prepare_input_text(&request))
            .await?;

        if let Some(cache) = &self.cache {
            let key = Tag::prepare_cache_key(&request);

            if let Some(val) = cache.get_de::<Tag::Response>(key.as_str()) {
                debug!("Cache hit for: {key}");
                Ok(val)
            } else {
                debug!("Cache missed for: {key}");
                let res = Tag::execute_request(d, request).await?;
                cache.set_ser(&key, &res)?;
                Ok(res)
            }
        } else {
            Tag::execute_request(d, request).await
        }
    }
}

impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            providers: DashMap::default(),
            groups: DashMap::default(),
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
    type Request;

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
    use crate::provider::dummy::DummyProvider;
    use crate::models::dummy::DummyModel;

    #[tokio::test]
    async fn test_router_reranker_with_dummy() {
        let router = Router::<RerankerTag>::default();

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        let model = DummyModel::new("reranker".to_string(), provider)
            .with_reranker_responses(vec![
                vec![(0, 0.95), (2, 0.87), (1, 0.72)],
            ]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn RerankerModel>);
        router
            .add_deployment("rank".into(), deployment)
            .unwrap();

        let request = RerankerRequest {
            query: "What is Rust?".to_string(),
            documents: vec![
                "Rust is a systems language".to_string(),
                "Python is scripting".to_string(),
                "Rust memory safety".to_string(),
            ],
        };

        let result = router
            .invoke_cached("rank".into(), request)
            .await
            .unwrap();

        assert_eq!(result, vec![(0, 0.95), (2, 0.87), (1, 0.72)]);
    }

    #[tokio::test]
    async fn test_router_reranker_cache_hit() {
        let cache_dir = tempfile::tempdir().unwrap();
        let db_path = cache_dir.path().join("reranker-cache.db");

        let router = Router::<RerankerTag>::with_cache(&db_path).unwrap();

        // Verify TieredCache can store and retrieve a Ranking
        {
            let cache = router.cache.as_ref().unwrap();
            let test_ranking: Ranking = vec![(0, 0.95), (1, 0.8)];
            cache.set_ser("test_key", &test_ranking).unwrap();
            let retrieved = cache.get_de::<Ranking>("test_key");
            assert_eq!(retrieved, Some(test_ranking), "TieredCache roundtrip failed");
        }

        let provider = Arc::new(DummyProvider::default());
        router.add_or_update_provider(provider.clone());

        // Configure only one response — cache must serve it on the second call
        let model = DummyModel::new("reranker".to_string(), provider)
            .with_reranker_responses(vec![
                vec![(0, 0.9)],
            ]);

        let deployment = Deployment::new(Box::new(model) as Box<dyn RerankerModel>);
        router
            .add_deployment("rank".into(), deployment)
            .unwrap();

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
        let second = router
            .invoke_cached("rank".into(), request)
            .await
            .unwrap();
        assert_eq!(first, second);
    }
}
