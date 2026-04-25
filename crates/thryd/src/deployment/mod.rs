//! Deployment wrapper with usage tracking and rate limiting.
//!
//! This module provides a [`Deployment`] wrapper that adds quota management,
//! rate limiting, and usage tracking to any model implementation.
//!
//! # Usage
//!
//! Deployments are typically created through a [`Router`] and used to manage
//! LLM requests with built-in RPM/TPM quotas.
//!
//! ```ignore
//! use thryd::{Deployment, OpenaiModel};
//! use secrecy::SecretString;
//! use std::sync::Arc;
//!
//! let provider = Arc::new(OpenaiCompatible::openai(api_key));
//! let model = OpenaiModel::new("gpt-4".to_string(), provider);
//!
//! let deployment = Deployment::new(Box::new(model))
//!     .with_usage_constrain(
//!         Some(60),      // 60 requests per minute
//!         Some(100_000), // 100,000 tokens per minute
//!     );
//! ```
//!
//! [`Router`]: crate::route::Router

use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::tracker::count_token;
use crate::{
    Completion, Embeddings, Ranking, RerankerModel, RerankerRequest, Result, UsageTracker,
};
use tokio::sync::Mutex;
use tokio::time::{Duration, sleep};

/// Macro for automatically tracking usage when a request succeeds.
///
/// This macro wraps async operations and records input/output to the usage tracker
/// if the result is `Ok`. It handles both single-output (embedding, rerank) and
/// dual-output (completion with both request and response) tracking patterns.
///
/// # Arguments
///
/// - `$tracker`: The `Mutex<UsageTracker>` to record usage to
/// - `$input`: The input text/prompt to count tokens for
/// - `$res`: The result of the operation
/// - `$output`: (optional) The response text for completion tracking
///
/// # Example
///
/// ```ignore
/// with_tracking!(tracker, input.clone(), res, response_string)
/// ```
macro_rules! with_tracking {
    ($tracker:expr, $input:expr, $res:expr) => {{
        if $res.is_ok() {
            $tracker
                .lock()
                .await
                .add_request_raw($input, "".to_string());
        }
        $res
    }};
    ($tracker:expr, $input:expr, $res:expr, $output:expr) => {{
        if $res.is_ok() {
            $tracker.lock().await.add_request_raw($input, $output);
        }
        $res
    }};
}

/// A deployment wrapper that adds usage tracking and rate limiting to a model.
///
/// `Deployment<M>` wraps any model implementing the [`Model`] trait and provides:
/// - Configurable RPM (requests per minute) and TPM (tokens per minute) quotas
/// - Automatic usage tracking for all requests
/// - Capacity checking and wait-for-capacity operations
/// - Unified interface for completion, embedding, and reranking
///
/// # Type Parameters
///
/// - `M`: The underlying model type that implements `Model` (and optionally
///   `CompletionModel`, `EmbeddingModel`, or `RerankerModel`)
///
/// # Example
///
/// ```ignore
/// use thryd::{Deployment, OpenaiModel, OpenaiCompatible};
/// use secrecy::SecretString;
///
/// let api_key = SecretString::from("sk-...".to_string());
/// let provider = Arc::new(OpenaiCompatible::openai(api_key));
/// let model = OpenaiModel::new("gpt-4".to_string(), provider);
///
/// let deployment = Deployment::new(Box::new(model))
///     .with_usage_constrain(
///         Some(60),      // 60 RPM
///         Some(100_000), // 100k TPM
///     );
///
/// // Check if deployment has capacity
/// if deployment.is_ready().await {
///     let response = deployment.completion(request).await?;
/// }
/// ```
///
/// [`Model`]: crate::model::Model
pub struct Deployment<M: ?Sized + Model> {
    /// The underlying model being wrapped
    model: Box<M>,
    /// Optional usage tracker for rate limiting (RPM/TPM quotas)
    usage_tracker: Option<Mutex<UsageTracker>>,
}

impl<M: ?Sized + Model> Deployment<M> {
    /// Creates a new `Deployment` wrapping the given model.
    ///
    /// The deployment starts without usage tracking. Use [`with_usage_constrain`]
    /// to add rate limiting after creation.
    ///
    /// # Arguments
    ///
    /// * `model` - A boxed model instance to wrap
    ///
    /// # Example
    ///
    /// ```ignore
    /// let deployment = Deployment::new(Box::new(model));
    /// ```
    ///
    /// [`with_usage_constrain`]: Deployment::with_usage_constrain
    pub fn new(model: Box<M>) -> Deployment<M> {
        Self {
            model,
            usage_tracker: None,
        }
    }

    /// Returns the model identifier string.
    ///
    /// This delegates to the wrapped model's [`Model::identifier`] method.
    ///
    /// # Example
    ///
    /// ```ignore
    /// let id = deployment.identifier();
    /// println!("Using model: {id}");
    /// ```
    pub fn identifier(&self) -> String {
        self.model.identifier()
    }

    /// Configures RPM (requests per minute) and/or TPM (tokens per minute) quotas.
    ///
    /// When quotas are set, the deployment will track usage and enforce rate limits.
    /// If no tracker is configured (i.e., this method not called), all operations
    /// pass through without rate limiting.
    ///
    /// # Arguments
    ///
    /// * `rpm` - Requests per minute limit (None to disable RPM limiting)
    /// * `tpm` - Tokens per minute limit (None to disable TPM limiting)
    ///
    /// # Example
    ///
    /// ```ignore
    /// let deployment = Deployment::new(Box::new(model))
    ///     .with_usage_constrain(
    ///         Some(60),      // Max 60 requests per minute
    ///         Some(100_000), // Max 100,000 tokens per minute
    ///     );
    /// ```
    pub fn with_usage_constrain(mut self, rpm: Option<u64>, tpm: Option<u64>) -> Self {
        self.usage_tracker = Some(Mutex::new(UsageTracker::with_quota(tpm, rpm)));
        self
    }

    /// Checks if the deployment has capacity for new requests.
    ///
    /// Returns `true` if there is no rate limit configured, or if both RPM and TPM
    /// quotas have remaining capacity. Returns `false` if at least one quota is exceeded.
    ///
    /// # Example
    ///
    /// ```ignore
    /// if deployment.is_ready().await {
    ///     // Safe to make a request
    ///     let response = deployment.completion(request).await?;
    /// }
    /// ```
    pub async fn is_ready(&self) -> bool {
        if let Some(tracker) = &self.usage_tracker {
            tracker.lock().await.has_capacity()
        } else {
            true
        }
    }

    /// Blocks until capacity is available for the given input.
    ///
    /// If no rate limits are configured, this returns immediately. Otherwise,
    /// it calculates the token count of the input and waits until both RPM and TPM
    /// quotas have capacity for a request of that size.
    ///
    /// # Arguments
    ///
    /// * `input_text` - The text to calculate token count for TPM tracking
    ///
    /// # Returns
    ///
    /// Returns `Ok(&self)` when capacity is available, or an error if the
    /// operation fails while waiting.
    ///
    /// # Example
    ///
    /// ```ignore
    /// // Wait up to capacity before making a request
    /// deployment.wait_capacity_for("Hello, world!".to_string()).await?;
    /// let response = deployment.completion(request).await?;
    /// ```
    pub async fn wait_capacity_for(&self, input_text: String) -> Result<&Self> {
        if let Some(tracker) = &self.usage_tracker {
            let need = count_token(input_text);
            while let time = tracker.lock().await.need_wait_for(need)
                && time > 0
            {
                sleep(Duration::from_millis(time)).await;
            }
            Ok(self)
        } else {
            Ok(self)
        }
    }

    /// Calculates the minimum cooldown time needed before a request can proceed.
    ///
    /// This is useful for pre-flight checks without actually blocking. Returns
    /// the minimum milliseconds to wait before the rate limit tracker would
    /// accept a new request of the given input size.
    ///
    /// # Arguments
    ///
    /// * `input_text` - The text to calculate token count for TPM tracking
    ///
    /// # Returns
    ///
    /// Milliseconds to wait. Returns `0` if no rate limits are configured
    /// or if capacity is immediately available.
    ///
    /// # Example
    ///
    /// ```ignore
    /// let wait_time = deployment.min_cooldown_time(prompt.clone()).await;
    /// if wait_time > 0 {
    ///     println!("Rate limit hit. Wait {}ms", wait_time);
    ///     sleep(Duration::from_millis(wait_time)).await;
    /// }
    /// ```
    pub async fn min_cooldown_time(&self, input_text: String) -> u64 {
        if let Some(tracker) = &self.usage_tracker {
            tracker.lock().await.need_wait_for_string(input_text)
        } else {
            0
        }
    }

    /// Makes a completion request through the deployment.
    ///
    /// Requires the wrapped model to implement [`CompletionModel`]. If usage
    /// tracking is configured, both input tokens and output tokens are recorded.
    ///
    /// # Arguments
    ///
    /// * `request` - The completion request parameters
    ///
    /// # Example
    ///
    /// ```ignore
    /// let request = CompletionRequest {
    ///     message: "What is Rust?".to_string(),
    ///     top_p: 0.9,
    ///     temperature: 0.7,
    ///     stream: false,
    ///     max_completion_tokens: 100,
    ///     presence_penalty: 0.0,
    ///     frequency_penalty: 0.0,
    /// };
    ///
    /// let response = deployment.completion(request).await?;
    /// ```
    ///
    /// [`CompletionModel`]: crate::model::CompletionModel
    pub async fn completion(&self, request: CompletionRequest) -> Result<Completion>
    where
        M: CompletionModel,
    {
        if let Some(tracker) = &self.usage_tracker {
            let input = request.message.clone();
            let res = self.model.completion(request).await;
            with_tracking!(
                tracker,
                input,
                res,
                res.as_ref().map(|r| r.to_string()).unwrap_or_default()
            )
        } else {
            self.model.completion(request).await
        }
    }

    /// Makes an embedding request through the deployment.
    ///
    /// Requires the wrapped model to implement [`EmbeddingModel`]. If usage
    /// tracking is configured, input tokens are recorded (embeddings have no output).
    ///
    /// # Arguments
    ///
    /// * `request` - The embedding request parameters
    ///
    /// # Example
    ///
    /// ```ignore
    /// let request = EmbeddingRequest {
    ///     texts: vec![
    ///         "Hello, world!".to_string(),
    ///         "How are you?".to_string(),
    ///     ],
    /// };
    ///
    /// let embeddings = deployment.embedding(request).await?;
    /// ```
    ///
    /// [`EmbeddingModel`]: crate::model::EmbeddingModel
    pub async fn embedding(&self, request: EmbeddingRequest) -> Result<Embeddings>
    where
        M: EmbeddingModel,
    {
        if let Some(tracker) = &self.usage_tracker {
            let input = request.texts.iter().cloned().collect();
            let res = self.model.embedding(request).await;
            with_tracking!(tracker, input, res)
        } else {
            self.model.embedding(request).await
        }
    }

    /// Makes a reranking request through the deployment.
    ///
    /// Requires the wrapped model to implement [`RerankerModel`]. If usage
    /// tracking is configured, document tokens are recorded.
    ///
    /// # Arguments
    ///
    /// * `request` - The reranking request parameters
    ///
    /// # Example
    ///
    /// ```ignore
    /// let request = RerankerRequest {
    ///     documents: vec!["doc1".to_string(), "doc2".to_string()],
    ///     query: "What is Rust?".to_string(),
    ///     top_n: Some(2),
    /// };
    ///
    /// let ranking = deployment.rerank(request).await?;
    /// ```
    ///
    /// [`RerankerModel`]: crate::model::RerankerModel
    pub async fn rerank(&self, request: RerankerRequest) -> Result<Ranking>
    where
        M: RerankerModel,
    {
        if let Some(tracker) = &self.usage_tracker {
            let input = request.documents.iter().cloned().collect();
            let res = self.model.rerank(request).await;
            with_tracking!(tracker, input, res)
        } else {
            self.model.rerank(request).await
        }
    }
}
