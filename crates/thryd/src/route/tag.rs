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
//! - `EvaluationTag` — state evaluation, with the `jev` feature on

use crate::Result;
use crate::deployment::Deployment;
use crate::model::{
    CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model, WithUsage,
};
#[cfg(feature = "jev")]
use crate::model::{EvaluationModel, EvaluationRequest, EvaluationResponse};
use crate::provider::Provider;
use crate::{
    CompletionResponse, Embedding, EmbeddingResponse, PersistentCache, RankingResponse,
    RerankerModel, RerankerRequest,
};
use async_trait::async_trait;
#[cfg(feature = "jev")]
use serde::Deserialize;
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::sync::Arc;
use strum_macros::Display;

use super::{CachePolicy, ModelName};

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

    /// Whether a successful response is safe to persist in the cache.
    ///
    /// Default: cache everything. Override for response types where an
    /// empty payload is a degenerate outcome (e.g. a completion that
    /// returned no content — provider refusal, content filter, truncated
    /// stream): caching it would serve that empty result forever.
    fn cache_worthy(response: &Self::Response) -> bool {
        let _ = response;
        true
    }

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
        response.usage()
    }

    async fn single_cached(
        cache: &PersistentCache,
        key: &str,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
        policy: CachePolicy,
    ) -> Result<Self::Response> {
        if let Some(val) = cache
            .get_de::<Self::Response>(key)
            .inspect(|_val| tracing::trace!("Cache hit for: {key}"))
        {
            Ok(val)
        } else {
            let res = Self::execute_request(deployment, request.clone()).await;
            if let Ok(val) = res.as_ref() {
                if !Self::cache_worthy(val) {
                    tracing::warn!("Empty response content; not caching key: {key}");
                } else if policy.no_store {
                    tracing::debug!("no_store is set; not caching key: {key}");
                } else {
                    cache.set_ser(key, val)?;
                }
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
        policy: CachePolicy,
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

        if policy.no_store {
            tracing::debug!(
                "no_store is set; not caching {} missed value(s)",
                missed_indices.len()
            );
        } else {
            missed_indices
                .iter()
                .zip(new_vals.iter())
                .try_for_each(|(&i, val)| cache.set_ser(keys[i.to_owned()].as_str(), val))?;
        }

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
    ///
    /// `policy` gates the write side: reads are always attempted when a cache
    /// is present, writes are skipped when [`CachePolicy::no_store`] is set.
    async fn cache_resolve(
        cache: &Option<PersistentCache>,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
        policy: CachePolicy,
    ) -> Result<Self::Response> {
        if let Some(cache) = cache {
            let key = Self::cache_key(&request);
            match &key {
                CacheKey::Single(k) => {
                    Self::single_cached(cache, k.as_str(), deployment, request, policy).await
                }
                CacheKey::Batch(ks) => {
                    Self::batch_cached(cache, ks.as_slice(), deployment, request, policy).await
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
/// }, CachePolicy::default()).await?;
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
/// }, CachePolicy::default()).await?;
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
/// }, CachePolicy::default()).await?;
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

/// Tag type for evaluation models.
///
/// Use with [`Router<EvaluationTag>`](super::Router) to evaluate a state against named questions:
/// one deployment answers the whole set in one call, and the answers are cached under the state,
/// the model and the questions that produced them.
///
/// # Example
///
/// ```ignore
/// use thryd::{CachePolicy, EvaluationRequest, EvaluationTag, Question};
///
/// let mut router = Router::<EvaluationTag>::default();
/// router.add_or_update_provider(jev);
/// router.deploy("eval", "typesafe/jev-1.13.0".into(), Some(60), None)?;
///
/// let request = EvaluationRequest::new("The payouts have been failing for 3 days.")
///     .with_question("is_urgent", Question::noul("Does this convey urgency?"));
/// let answers = router.invoke("eval".into(), request, CachePolicy::default()).await?;
/// assert!(answers.noul("is_urgent").is_some_and(|urgent| urgent >= 0.9));
/// ```
#[cfg(feature = "jev")]
#[derive(Default)]
pub struct EvaluationTag;

#[cfg(feature = "jev")]
#[async_trait]
impl ModelTypeTag for EvaluationTag {
    type Model = dyn EvaluationModel;
    type Request = EvaluationRequest;
    type CacheVal = EvaluationResponse;
    type Response = EvaluationResponse;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_evaluation_model(model_name)
    }

    fn cont_tokens(request: &Self::Request) -> u64 {
        // The state and the questions are the input; the API reports the exact count, so this is
        // the same text-shaped estimate the other tags work from.
        crate::count_token(serde_json::to_string(request).unwrap_or_default())
    }

    fn cache_key(request: &Self::Request) -> CacheKey {
        // The whole request is the key — state, model and every question — so two callers asking
        // different questions about one state never share answers, and a pinned model id keeps its
        // answers apart from the moving alias's.
        CacheKey::Single(
            blake3::hash(serde_json::to_vec(request).unwrap_or_default().as_slice()).to_string(),
        )
    }

    /// An evaluation that answered nothing is a degenerate result: never persist it.
    fn cache_worthy(response: &Self::Response) -> bool {
        !response.answers.is_empty()
    }

    /// Single-key caching, over the JSON copy of the response the client works in.
    ///
    /// Everything here is the trait's own single-key behaviour — read first, write on a miss
    /// unless [`CachePolicy::no_store`] is set, store nothing `cache_worthy` rejects — except for
    /// what travels through the cache: postcard cannot read back the tagged answer union the API
    /// returns, so the response is stored as the JSON it arrived as and decoded on the way out.
    async fn single_cached(
        cache: &PersistentCache,
        key: &str,
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
        policy: CachePolicy,
    ) -> Result<Self::Response> {
        if let Some(cached) = cache.get_de::<CachedEvaluation>(key) {
            tracing::trace!("Cache hit for: {key}");
            return cached.into_response();
        }

        let response = Self::execute_request(deployment, request).await;
        match response.as_ref() {
            Ok(response) if !Self::cache_worthy(response) => {
                tracing::warn!("Empty evaluation; not caching key: {key}");
            }
            Ok(_) if policy.no_store => {
                tracing::debug!("no_store is set; not caching key: {key}");
            }
            Ok(response) => cache.set_ser(key, &CachedEvaluation::from_response(response)?)?,
            Err(_) => {}
        }
        response
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.evaluate(request).await
    }
}

/// An evaluation as the cache stores it: the client's response, as the JSON it arrived as.
///
/// [`EvaluationResponse`] cannot cross the cache's binary codec directly — an internally tagged
/// answer union is not something postcard can read back — so the response travels as the text the
/// API sent and is decoded again on the way out. Nothing else about the cache changes: the key is
/// still the request's content hash, and the value is still one opaque payload.
#[cfg(feature = "jev")]
#[derive(Clone, Serialize, Deserialize)]
struct CachedEvaluation(String);

#[cfg(feature = "jev")]
impl CachedEvaluation {
    /// The response, as it will be stored.
    fn from_response(response: &EvaluationResponse) -> Result<Self> {
        Ok(Self(serde_json::to_string(response)?))
    }

    /// The response this was made from.
    fn into_response(self) -> Result<EvaluationResponse> {
        Ok(serde_json::from_str(&self.0)?)
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
        // Keyed on each image's digest — taken over the original bytes, before any
        // compression — so re-encoding settings never fork the cache.
        let key = if request.images.is_empty() {
            blake3::hash(request.message.as_bytes()).to_string()
        } else {
            let mut s = request.message.clone();
            for img in &request.images {
                s.push_str(&img.digest);
            }
            blake3::hash(s.as_bytes()).to_string()
        };

        CacheKey::Single(key)
    }

    /// An empty completion (no content — refusal, content filter, truncated
    /// stream) is a degenerate result: never persist it.
    fn cache_worthy(response: &Self::Response) -> bool {
        !response.content.trim().is_empty()
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
            max_batch_emb_size: request.max_batch_emb_size,
        }
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
    #[cfg(feature = "jev")]
    use crate::Router;
    use crate::model::{CompletionRequest, ImageAttachment};

    /// Two compression settings for the same original image must key the same: the
    /// key follows the digest taken before compression, not the sent payload.
    #[test]
    fn completion_cache_key_follows_the_original_digest() {
        let key_of = |request: &CompletionRequest| match CompletionTag::cache_key(request) {
            CacheKey::Single(k) => k,
            CacheKey::Batch(_) => unreachable!("completion keys are single"),
        };
        let request_with = |uri: &str, digest: &str| CompletionRequest {
            message: "look at this".to_string(),
            images: vec![ImageAttachment {
                uri: uri.to_string(),
                digest: digest.to_string(),
            }],
            ..Default::default()
        };

        let digest = blake3::hash(b"original bytes").to_string();
        let compressed = key_of(&request_with("data:image/jpeg;base64,AAAA", &digest));
        let untouched = key_of(&request_with("data:image/png;base64,BBBBBBBB", &digest));
        assert_eq!(compressed, untouched);

        let other = key_of(&request_with(
            "data:image/jpeg;base64,AAAA",
            &blake3::hash(b"another image").to_string(),
        ));
        assert_ne!(other, compressed);
    }

    #[cfg(feature = "jev")]
    fn evaluation_request() -> EvaluationRequest {
        EvaluationRequest::new("The payouts have been failing for 3 days.").with_question(
            "is_urgent",
            crate::model::EvaluationQuestion::noul("Does this convey urgency?"),
        )
    }

    /// A router whose one deployment answers with `answers`, seeded through the dummy model the
    /// way the seeding helpers do it, so routing, usage recording and caching are what is tested.
    #[cfg(feature = "jev")]
    fn evaluation_router(answers: Vec<EvaluationResponse>) -> Router<EvaluationTag> {
        let model = crate::DummyModel::default().with_evaluation_responses(answers);
        let router = Router::<EvaluationTag>::default();
        router
            .add_deployment("eval".to_string(), Deployment::new(Box::new(model)))
            .expect("a new group accepts its first deployment");
        router
    }

    #[cfg(feature = "jev")]
    #[tokio::test]
    async fn evaluation_tag_routes_through_a_deployment() {
        let router = evaluation_router(vec![crate::models::jev::test_response(0.95)]);

        let answers = router
            .invoke(
                "eval".to_string(),
                evaluation_request(),
                CachePolicy::CACHED,
            )
            .await
            .expect("the dummy model answers");

        assert_eq!(answers.noul("is_urgent"), Some(0.95));
        assert_eq!(answers.model.as_str(), "jev-test");
        assert_eq!(answers.usage().unwrap().total_tokens, 15);
    }

    /// The key covers the state, the model and the questions, and an answer is served from the
    /// cache: the dummy queue holds one response, so the second call can only come from there.
    #[cfg(feature = "jev")]
    #[tokio::test]
    async fn evaluation_answers_are_cached_under_the_request() {
        let dir = tempfile::tempdir().expect("a temporary directory");
        let router = Router::<EvaluationTag>::with_cache(dir.path().join("evaluations"))
            .expect("the cache directory is created");
        router
            .add_deployment(
                "eval".to_string(),
                Deployment::new(Box::new(
                    crate::DummyModel::default()
                        .with_evaluation_responses(vec![crate::models::jev::test_response(0.95)]),
                )),
            )
            .expect("a new group accepts its first deployment");

        let answers = router
            .invoke(
                "eval".to_string(),
                evaluation_request(),
                CachePolicy::CACHED,
            )
            .await
            .expect("the dummy model answers");
        let cached = router
            .invoke(
                "eval".to_string(),
                evaluation_request(),
                CachePolicy::CACHED,
            )
            .await
            .expect("the second request is served from the cache");

        assert_eq!(cached, answers);

        let other_state = EvaluationRequest::new("Another state").with_question(
            "is_urgent",
            crate::model::EvaluationQuestion::noul("Does this convey urgency?"),
        );
        assert!(
            router
                .invoke("eval".to_string(), other_state, CachePolicy::CACHED)
                .await
                .is_err(),
            "a different state must not be served the cached answer"
        );
    }

    /// An evaluation the provider answered with nothing must not become the cache's answer.
    #[cfg(feature = "jev")]
    #[tokio::test]
    async fn an_empty_evaluation_is_not_cached() {
        let dir = tempfile::tempdir().expect("a temporary directory");
        let empty = EvaluationResponse {
            model: crate::model::EvaluationModelName::from("jev-test"),
            answers: std::collections::BTreeMap::new(),
            usage: jevlin::Usage {
                input_tokens: 0,
                output_tokens: 0,
            },
        };
        let router = Router::<EvaluationTag>::with_cache(dir.path().join("evaluations"))
            .expect("the cache directory is created");
        router
            .add_deployment(
                "eval".to_string(),
                Deployment::new(Box::new(
                    crate::DummyModel::default().with_evaluation_responses(vec![empty]),
                )),
            )
            .expect("a new group accepts its first deployment");

        assert!(
            router
                .invoke(
                    "eval".to_string(),
                    evaluation_request(),
                    CachePolicy::CACHED
                )
                .await
                .is_ok()
        );
        assert!(
            router
                .invoke(
                    "eval".to_string(),
                    evaluation_request(),
                    CachePolicy::CACHED
                )
                .await
                .is_err(),
            "the empty answer must not have been persisted"
        );
    }
}
