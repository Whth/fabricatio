//! Model type tags and the [`ModelTypeTag`] trait.
//!
//! This module defines the **type-level tag pattern** for routing: each model type
//! (completion, embedding, reranker) gets a zero-sized tag struct that implements
//! [`ModelTypeTag`], specifying how to create models, build cache keys, and execute
//! requests.
//!
//! # Tags
//!
//! - [`CompletionTag`] — text generation via [`CompletionModel`](crate::model::CompletionModel)
//! - [`EmbeddingTag`] — text vectorization via [`EmbeddingModel`](crate::model::EmbeddingModel)
//! - [`RerankerTag`] — document reranking via [`RerankerModel`](crate::RerankerModel)

use crate::Result;
use crate::deployment::Deployment;
use crate::model::{
    CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model, WithUsage,
};
use crate::provider::Provider;
use crate::{
    CompletionResponse, Embedding, EmbeddingResponse, PersistentCache, RankingResponse,
    RerankerModel, RerankerRequest,
};
use async_trait::async_trait;
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::sync::Arc;
use strum_macros::Display;

use super::ModelName;

#[derive(Debug, Clone, Display)]
pub enum CacheKey {
    Single(String),
    Batch(Vec<String>),
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
/// use thryd::{Result, ThrydError, route::{ModelTypeTag, DeploymentEntry}};
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

    type CacheVal: DeserializeOwned + Serialize + Clone + Sync + Send;

    /// The response type for this model type.
    /// Must support serialization for caching and deserialization for cache retrieval.
    /// Must implement [`WithUsage`] for usage tracking.
    type Response: DeserializeOwned + Serialize + Clone + WithUsage;
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

    fn cont_tokens(request: &Self::Request) -> u64;

    fn cache_key(request: &Self::Request) -> CacheKey;

    #[inline]
    fn recover_batch_request(_cache_vals: Vec<Self::CacheVal>) -> Self::Response {
        unimplemented!()
    }

    #[inline]
    fn breakdown_batch_response(_response: Self::Response) -> Vec<Self::CacheVal> {
        unimplemented!()
    }

    /// Total tokens consumed by this response (prompt + completion), with fallback.
    ///
    /// Uses API-reported `Usage.total_tokens` when available. Tags that can
    /// estimate output tokens from content (e.g. completion text) override
    /// this to provide a fallback for streaming or providers that don't report usage.
    fn total_response_tokens(response: &Self::Response) -> u64 {
        Self::response_usage(response)
            .filter(|u| u.total_tokens > 0)
            .map(|u| u.total_tokens as u64)
            .unwrap_or(0)
    }

    /// Extract API-reported usage from a response via [`WithUsage`].
    #[inline]
    fn response_usage(response: &Self::Response) -> Option<crate::model::Usage> {
        response.usage().cloned()
    }

    async fn single_cached(
        cache: &PersistentCache,
        key: &str,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        if let Some(val) = cache
            .get_de::<Self::Response>(key)
            .inspect(|_val| tracing::trace!("Cache hit for: {key}"))
        {
            Ok(val)
        } else {
            let res = Self::execute_request(deployment, request.clone()).await;
            if let Ok(val) = res.as_ref() {
                cache.set_ser(key, val)?;
            };
            res
        }
    }

    #[inline]
    fn build_missed_batch_request(_request: Self::Request, _indices: &[&usize]) -> Self::Request {
        unimplemented!()
    }

    async fn batch_cached(
        cache: &PersistentCache,
        keys: &[String],
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        let indexed_vals = keys
            .iter()
            .enumerate()
            .map(|(i, key)| (i, cache.get_de::<Self::CacheVal>(key)))
            .collect::<Vec<_>>();

        let (hits, missed): (Vec<_>, Vec<_>) =
            indexed_vals.into_iter().partition(|(_, val)| val.is_some());

        if missed.is_empty() {
            let cached_vals = hits.into_iter().map(|(_, val)| val.unwrap()).collect();
            return Ok(Self::recover_batch_request(cached_vals));
        }

        let missed_indices = missed.iter().map(|(i, _)| i).collect::<Vec<_>>();
        let missed_request = Self::build_missed_batch_request(request, &missed_indices);
        let resp = Self::execute_request(deployment, missed_request).await?;

        let new_vals = Self::breakdown_batch_response(resp);

        missed_indices
            .iter()
            .zip(new_vals.iter())
            .try_for_each(|(&i, val)| cache.set_ser(keys[i.to_owned()].as_str(), val))?;

        let mut total_vals = new_vals
            .into_iter()
            .zip(missed_indices.into_iter().cloned())
            .collect::<Vec<_>>();
        total_vals.extend(hits.into_iter().map(|(i, val)| (val.unwrap(), i)));
        total_vals.sort_by_key(|(_, i)| *i);
        Ok(Self::recover_batch_request(
            total_vals
                .into_iter()
                .map(|(val, _)| val)
                .collect::<Vec<_>>(),
        ))
    }

    /// Each tag defines its own caching strategy. Default: batch-level.
    /// Override for per-item sparse caching.
    async fn cache_resolve(
        cache: &Option<PersistentCache>,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        if let Some(cache) = cache {
            let key = Self::cache_key(&request);
            match &key {
                CacheKey::Single(k) => {
                    Self::single_cached(cache, k.as_str(), deployment, request).await
                }
                CacheKey::Batch(ks) => {
                    Self::batch_cached(cache, ks.as_slice(), deployment, request).await
                }
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
/// Use with [`Router<CompletionTag>`](super::Router) for text generation requests.
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
/// Use with [`Router<EmbeddingTag>`](super::Router) for text embedding requests.
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
/// Use with [`Router<RerankerTag>`](super::Router) for document reranking requests.
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
    type CacheVal = RankingResponse;
    type Response = RankingResponse;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_reranker_model(model_name)
    }

    fn cont_tokens(request: &Self::Request) -> u64 {
        let mut t_seq = request.documents.clone();
        t_seq.push(request.query.clone());
        t_seq.sort();
        crate::count_token(t_seq.concat())
    }

    fn cache_key(request: &Self::Request) -> CacheKey {
        let mut t_seq = request.documents.clone();
        t_seq.push(request.query.clone());
        t_seq.sort();
        CacheKey::Single(blake3::hash(t_seq.concat().as_bytes()).to_string())
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
    type CacheVal = CompletionResponse;
    type Response = CompletionResponse;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_completion_model(model_name)
    }

    fn cont_tokens(request: &Self::Request) -> u64 {
        crate::count_token(request.message.clone())
    }

    fn cache_key(request: &Self::Request) -> CacheKey {
        let key = if request.images.is_empty() {
            blake3::hash(request.message.as_bytes()).to_string()
        } else {
            let mut s = request.message.clone();
            for img in &request.images {
                s.push_str(img);
            }
            blake3::hash(s.as_bytes()).to_string()
        };
        CacheKey::Single(key)
    }

    fn total_response_tokens(response: &Self::Response) -> u64 {
        Self::response_usage(response)
            .filter(|u| u.total_tokens > 0)
            .map(|u| u.total_tokens as u64)
            .unwrap_or_else(|| crate::count_token(response.content.clone()))
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
    type CacheVal = Embedding;
    type Response = EmbeddingResponse;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_embedding_model(model_name)
    }

    fn cont_tokens(request: &Self::Request) -> u64 {
        let mut t_seq = request.texts.clone();
        t_seq.sort();
        crate::count_token(t_seq.concat())
    }

    fn cache_key(request: &Self::Request) -> CacheKey {
        CacheKey::Batch(
            request
                .texts
                .iter()
                .map(|t| format!("emb:{}:{}", request.ndim, blake3::hash(t.as_bytes())))
                .collect(),
        )
    }

    fn recover_batch_request(cache_vals: Vec<Self::CacheVal>) -> Self::Response {
        EmbeddingResponse {
            embeddings: cache_vals,
            usage: crate::model::Usage::default(),
        }
    }

    fn breakdown_batch_response(response: Self::Response) -> Vec<Self::CacheVal> {
        response.embeddings
    }

    fn build_missed_batch_request(request: Self::Request, indices: &[&usize]) -> Self::Request {
        EmbeddingRequest {
            texts: indices.iter().map(|&&i| request.texts[i].clone()).collect(),
            ndim: request.ndim,
        }
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.embedding(request).await
    }
}
