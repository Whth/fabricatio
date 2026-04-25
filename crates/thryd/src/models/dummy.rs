//! Dummy model implementation for testing.
//!
//! This module provides a [`DummyModel`] that returns pre-configured mock responses,
//! making it ideal for unit testing without making actual API calls.
//!
//! # Purpose
//!
//! `DummyModel` allows you to:
//! - Test business logic without network calls
//! - Mock specific response sequences
//! - Simulate API responses for error handling tests
//! - Ensure deterministic behavior in CI/CD pipelines
//!
//! # Reranker Support
//!
//! `DummyModel` also supports reranker responses via [`RerankerModel`]:
//!
//! ```ignore
//! use thryd::{DummyModel, RerankerRequest, Ranking};
//! use std::sync::Arc;
//!
//! let model = DummyModel::new("reranker".to_string(), Arc::new(DummyProvider::default()))
//!     .with_reranker_responses(vec![
//!         vec![(0, 0.95), (2, 0.87), (1, 0.72)],  // (doc_idx, score)
//!     ]);
//! ```
//!
//! See individual method docs for LIFO queue behavior.

use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::dummy::DummyProvider;
use crate::provider::Provider;
use crate::{Completion, Embeddings, Ranking, RerankerModel, RerankerRequest};
use async_trait::async_trait;
use std::sync::{Arc, Mutex};

/// A mock model that returns pre-configured responses for testing.
///
/// `DummyModel` simulates an LLM by returning queued responses without
/// making any network requests. Responses are returned in LIFO (last-in-first-out)
/// order - the last added response is returned first.
///
/// # Type Parameters
///
/// - `provider` - Ignored; included for API compatibility but never used
///
/// # Response Exhaustion
///
/// Once all queued responses are consumed, subsequent calls will return
/// `ThrydError::Internal` with the message "DummyModel exhausted: no more
/// [completion/embedding] responses configured."
///
/// # Thread Safety
///
/// All operations use internal mutex locks for thread-safe access to the
/// response queues.
///
/// # Example
///
/// ```ignore
/// use thryd::{DummyModel, CompletionRequest, EmbeddingRequest};
/// use std::sync::Arc;
///
/// // Create a dummy model with completion responses
/// let model = DummyModel::new("test".to_string(), Arc::new(DummyProvider::default()))
///     .with_completion_responses(vec![
///         "First response".to_string(),
///         "Second response".to_string(),
///     ]);
///
/// // Use in tests
/// let response = model.completion(CompletionRequest::default()).await?;
/// assert_eq!(response, "Second response"); // LIFO order!
/// ```
pub struct DummyModel {
    name: String,
    response_q_string: Mutex<Vec<Completion>>,
    response_q_vec: Mutex<Vec<Embeddings>>,
    /// Queue for reranker responses, consumed in LIFO order.
    response_q_ranks: Mutex<Vec<Ranking>>,
    provider: Arc<dyn Provider>, // dummy model will not try to use provider to send req.
}

impl DummyModel {
    /// Creates a new `DummyModel` with empty response queues.
    ///
    /// # Arguments
    ///
    /// * `name` - Model identifier (returned by `model_name()`)
    /// * `provider` - Ignored; kept for API compatibility
    ///
    /// # Example
    ///
    /// ```ignore
    /// use thryd::{DummyModel, DummyProvider};
    /// use std::sync::Arc;
    ///
    /// let model = DummyModel::new(
    ///     "test-model".to_string(),
    ///     Arc::new(DummyProvider::default())
    /// );
    /// ```
    pub fn new(name: String, provider: Arc<dyn Provider>) -> Self {
        Self {
            name,
            response_q_string: Mutex::new(vec![]),
            response_q_vec: Mutex::new(vec![]),
            response_q_ranks: Mutex::new(vec![]),
            provider,
        }
    }

    /// Configures the completion response queue.
    ///
    /// Sets the list of responses to return for completion calls. Responses
    /// are consumed in LIFO order - the last element is returned first.
    ///
    /// # Arguments
    ///
    /// * `responses` - A vector of strings to return, in order of insertion
    ///
    /// # Example
    ///
    /// ```ignore
    /// use thryd::DummyModel;
    /// use std::sync::Arc;
    ///
    /// let model = DummyModel::new("test".to_string(), Arc::new(DummyProvider::default()))
    ///     .with_completion_responses(vec![
    ///         "Response A".to_string(),
    ///         "Response B".to_string(),
    ///         "Response C".to_string(),
    ///     ]);
    ///
    /// // First completion call returns "Response C"
    /// // Second completion call returns "Response B"
    /// // Third completion call returns "Response A"
    /// ```
    pub fn with_completion_responses(self, responses: Vec<Completion>) -> Self {
        *self.response_q_string.lock().unwrap() = responses;
        self
    }

    /// Configures the embedding response queue.
    ///
    /// Sets the list of embedding vectors to return for embedding calls.
    /// Responses are consumed in LIFO order - the last element is returned first.
    ///
    /// # Arguments
    ///
    /// * `responses` - A vector of embedding vectors. Each `Vec<Vec<f32>>` contains
    ///   the embeddings for one request (typically one embedding per text).
    ///
    /// # Example
    ///
    /// ```ignore
    /// use thryd::DummyModel;
    /// use std::sync::Arc;
    ///
    /// // Each response is a Vec of embeddings (one per text in request)
    /// let model = DummyModel::new("test".to_string(), Arc::new(DummyProvider::default()))
    ///     .with_embedding_responses(vec![
    ///         vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]],  // First response
    ///         vec![vec![0.7, 0.8, 0.9]],                         // Second response
    ///     ]);
    ///
    /// // First embedding call returns [[0.1,0.2,0.3], [0.4,0.5,0.6]]
    /// // Second embedding call returns [[0.7,0.8,0.9]]
    /// ```
    pub fn with_embedding_responses(self, responses: Vec<Embeddings>) -> Self {
        *self.response_q_vec.lock().unwrap() = responses;
        self
    }

    /// Configures the reranker response queue.
    ///
    /// Sets the list of ranking results to return for reranker calls.
    /// Responses are consumed in LIFO order - the last element is returned first.
    ///
    /// Each `Ranking` is a vector of `(document_index, score)` tuples,
    /// sorted by relevance score in descending order.
    ///
    /// # Arguments
    ///
    /// * `responses` - A vector of [`Ranking`] results, each containing
    ///   `(doc_idx, score)` pairs representing document relevance.
    ///
    /// # Example
    ///
    /// ```ignore
    /// use thryd::DummyModel;
    /// use std::sync::Arc;
    ///
    /// let model = DummyModel::new("test".to_string(), Arc::new(DummyProvider::default()))
    ///     .with_reranker_responses(vec![
    ///         vec![(0, 0.95), (2, 0.87), (1, 0.72)],  // First call returns this
    ///         vec![(1, 0.99), (0, 0.65)],           // Second call returns this
    ///     ]);
    ///
    /// // First rerank call returns [(0, 0.95), (2, 0.87), (1, 0.72)]
    /// // Second rerank call returns [(1, 0.99), (0, 0.65)]
    /// ```
    pub fn with_reranker_responses(self, responses: Vec<Ranking>) -> Self {
        *self.response_q_ranks.lock().unwrap() = responses;
        self
    }
}

impl Default for DummyModel {
    /// Creates a `DummyModel` with the name "dummy" and empty response queues.
    ///
    /// This is useful for quick test setup where responses will be configured later.
    ///
    /// # Example
    ///
    /// ```ignore
    /// let model = DummyModel::default();
    /// assert_eq!(model.model_name(), "dummy");
    ///
    /// // Configure responses before use
    /// let model = model.with_completion_responses(vec!["test".to_string()]);
    /// ```
    fn default() -> Self {
        Self::new("dummy".to_string(), Arc::new(DummyProvider::default()))
    }
}

impl Model for DummyModel {
    fn model_name(&self) -> &str {
        &self.name
    }

    fn provider(&self) -> Arc<dyn Provider> {
        self.provider.clone()
    }
}

/// # Completion Implementation
///
/// Implements [`CompletionModel`] for `DummyModel`, returning responses
/// from the pre-configured queue.
///
/// Responses are consumed in LIFO order. If the queue is empty, returns
/// `ThrydError::Internal` with an exhaustion message.
///
/// # Error
///
/// Returns `ThrydError::Internal("DummyModel exhausted: no more completion responses configured.")`
/// when the response queue is empty.
///
/// [`CompletionModel`]: crate::model::CompletionModel
#[async_trait]
impl CompletionModel for DummyModel {
    async fn completion(&self, _request: CompletionRequest) -> crate::Result<Completion> {
        let mut queue = self
            .response_q_string
            .lock()
            .map_err(|e| crate::ThrydError::Internal(e.to_string()))?;

        queue.pop().ok_or_else(|| {
            crate::ThrydError::Internal(
                "DummyModel exhausted: no more completion responses configured.".to_string(),
            )
        })
    }
}

/// # Embedding Implementation
///
/// Implements [`EmbeddingModel`] for `DummyModel`, returning responses
/// from the pre-configured queue.
///
/// Responses are consumed in LIFO order. If the queue is empty, returns
/// `ThrydError::Internal` with an exhaustion message.
///
/// # Error
///
/// Returns `ThrydError::Internal("DummyModel exhausted: no more embedding responses configured.")`
/// when the response queue is empty.
///
/// [`EmbeddingModel`]: crate::model::EmbeddingModel
#[async_trait]
impl EmbeddingModel for DummyModel {
    async fn embedding(&self, _request: EmbeddingRequest) -> crate::Result<Embeddings> {
        let mut queue = self
            .response_q_vec
            .lock()
            .map_err(|e| crate::ThrydError::Internal(e.to_string()))?;

        queue.pop().ok_or_else(|| {
            crate::ThrydError::Internal(
                "DummyModel exhausted: no more embedding responses configured.".to_string(),
            )
        })
    }
}

/// Implements [`RerankerModel`] for `DummyModel`, returning responses
/// from the pre-configured queue.
///
/// Responses are consumed in LIFO order. If the queue is empty, returns
/// `ThrydError::Internal` with an exhaustion message.
///
/// Each call pops a [`Ranking`] from the queue, which contains
/// `(document_index, score)` pairs sorted by relevance score descending.
///
/// # Error
///
/// Returns `ThrydError::Internal("DummyModel exhausted: no more reranker responses configured.")`
/// when the response queue is empty.
///
/// [`RerankerModel`]: crate::model::RerankerModel
#[async_trait]
impl RerankerModel for DummyModel {
    async fn rerank(&self, _request: RerankerRequest) -> crate::Result<Ranking> {
        self.response_q_ranks
            .lock()
            .map_err(|e| crate::ThrydError::Internal(e.to_string()))?
            .pop()
            .ok_or_else(|| {
                crate::ThrydError::Internal(
                    "DummyModel exhausted: no more reranker responses configured.".to_string(),
                )
            })
    }
}
