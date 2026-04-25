//! # Model Types and Traits
//!
//! This module defines the core request/response types and model traits for the Thryd LLM router.
//!
//! ## Request Types
//!
//! - [`EmbeddingRequest`] - Request payload for embedding generation
//! - [`CompletionRequest`] - Request payload for text completion
//! - [`RerankerRequest`] - Request payload for document reranking
//!
//! ## Model Traits
//!
//! - [`Model`] - Base trait providing model metadata
//! - [`CompletionModel`] - Trait for completion-generating models
//! - [`EmbeddingModel`] - Trait for embedding-generating models
//! - [`RerankerModel`] - Trait for reranking models
//!
//! ## Type Aliases
//!
//! - [`Ranking`] - Reranker output: ranked document indices with scores
//! - [`Embeddings`] - 2D vector of embedding floats
//! - [`Completion`] - Type alias for completion text output
//!
//! # Example
//!
//! ```ignore
//! use thryd::model::{CompletionRequest, CompletionModel, Model};
//! use thryd::provider::Provider;
//! use std::sync::Arc;
//!
//! // A custom completion model implementation
//! struct MyModel {
//!     name: String,
//!     provider: Arc<dyn Provider>,
//! }
//!
//! impl Model for MyModel {
//!     fn model_name(&self) -> &str { &self.name }
//!     fn provider(&self) -> Arc<dyn Provider> { self.provider.clone() }
//! }
//!
//! #[thryd::async_trait]
//! impl CompletionModel for MyModel {
//!     async fn completion(&self, request: CompletionRequest) -> thryd::Result<String> {
//!         // Custom implementation
//!         Ok("Hello, world!".to_string())
//!     }
//! }
//! ```

use crate::SEPARATE;
use crate::provider::Provider;
use async_trait::async_trait;
use serde::Serialize;
use std::sync::Arc;

/// Request payload for generating text embeddings.
///
/// Contains a batch of texts to encode into vector representations.
/// Use with [`EmbeddingModel`] implementations.
///
/// # Example
///
/// ```rust
/// use thryd::model::EmbeddingRequest;
///
/// let request = EmbeddingRequest {
///     texts: vec![
///         "The quick brown fox".to_string(),
///         "jumps over the lazy dog".to_string(),
///     ],
/// };
/// ```
#[derive(Debug, Clone, Serialize)]
pub struct EmbeddingRequest {
    /// The batch of text strings to encode into embeddings.
    /// Each string is encoded as a separate embedding vector.
    pub texts: Vec<String>,
}

/// Request payload for generating text completions.
///
/// Controls generation parameters like temperature, top_p, and token limits.
/// Use with [`CompletionModel`] implementations.
///
/// # Example
///
/// ```rust
/// use thryd::model::CompletionRequest;
///
/// let request = CompletionRequest {
///     message: "Explain recursion in programming".to_string(),
///     stream: false,
///     top_p: Some(0.9),
///     temperature: Some(0.7),
///     max_completion_tokens: Some(500),
///     presence_penalty: Some(0.0),
///     frequency_penalty: Some(0.0),
/// };
/// ```
#[derive(Debug, Clone, Serialize, Default)]
pub struct CompletionRequest {
    /// The input message/prompt to generate a completion for.
    pub message: String,

    /// Whether to stream the response. When `true`, returns a stream of chunks.
    pub stream: bool,

    /// Nucleus sampling threshold. Only sample from tokens comprising
    /// `top_p` probability mass. Range: (0, 1]. `None` uses provider default.
    pub top_p: Option<f32>,

    /// Sampling temperature. Higher values increase creativity. Range: [0, 2].
    /// `None` uses provider default (typically 0.7-1.0).
    pub temperature: Option<f32>,

    /// Maximum number of tokens in the completion. `None` uses provider default.
    pub max_completion_tokens: Option<u32>,

    /// Penalty for tokens that appear in the prompt. Range: [-2, 2].
    /// Positive values reduce repetition.
    pub presence_penalty: Option<f32>,

    /// Penalty for tokens proportional to their frequency in the prompt. Range: [-2, 2].
    /// Positive values reduce word repetition.
    pub frequency_penalty: Option<f32>,
}

/// Request payload for reranking documents against a query.
///
/// Takes a query and list of candidate documents, returns them ranked by relevance.
/// Use with [`RerankerModel`] implementations.
///
/// # Example
///
/// ```rust
/// use thryd::model::RerankerRequest;
///
/// let request = RerankerRequest {
///     query: "What is Rust?".to_string(),
///     documents: vec![
///         "Rust is a systems programming language".to_string(),
///         "Python is great for data science".to_string(),
///         "Rust memory safety guarantees".to_string(),
///     ],
/// };
/// ```
#[derive(Debug, Clone, Serialize)]
pub struct RerankerRequest {
    /// The query text to rank documents against.
    pub query: String,

    /// The list of candidate documents to rerank.
    pub documents: Vec<String>,
}

/// Type alias for reranker output.
///
/// A vector of `(document_index, relevance_score)` pairs, sorted by score descending.
/// Higher scores indicate greater relevance to the query.
pub type Ranking = Vec<(usize, f32)>;

/// Type alias for a batch of embedding vectors.
///
/// Each inner vector contains the embedding floats for one input text.
pub type Embeddings = Vec<Vec<f32>>;

/// Type alias for completion text output.
pub type Completion = String;

/// Base trait providing metadata for all model types.
///
/// Models must expose their name and associated provider.
/// The `identifier()` method returns a unique string combining both.
///
/// # Example
///
/// ```ignore
/// impl Model for MyModel {
///     fn model_name(&self) -> &str {
///         "my-custom-model"
///     }
///
///     fn provider(&self) -> Arc<dyn Provider> {
///         self.provider.clone()
///     }
/// }
/// ```
pub trait Model: Send + Sync {
    /// Returns the model identifier string (e.g., "gpt-4", "claude-3").
    fn model_name(&self) -> &str;

    /// Returns the provider instance for this model.
    fn provider(&self) -> Arc<dyn Provider>;

    /// Returns a unique identifier combining provider name and model name.
    ///
    /// Format: `{provider_name}{SEPARATE}{model_name}`
    /// Default implementation uses `provider.provider_name()` and `model_name()`.
    fn identifier(&self) -> String {
        format!(
            "{}{SEPARATE}{}",
            self.provider().provider_name(),
            self.model_name()
        )
    }
}

/// Trait for models that generate text completions.
///
/// Implement this trait to create custom completion model backends.
/// Use with [`crate::route::Router::<CompletionTag>`] for request routing.
///
/// # Example
///
/// ```ignore
/// #[thryd::async_trait]
/// impl CompletionModel for MyCompletionModel {
///     async fn completion(&self, request: CompletionRequest) -> thryd::Result<Completion> {
///         // Call your API and return the completion text
///         Ok("Generated text response".to_string())
///     }
/// }
/// ```
#[async_trait]
pub trait CompletionModel: Model {
    /// Generate a text completion for the given request.
    ///
    /// # Arguments
    /// * `request` - The completion request with prompt and generation parameters
    ///
    /// # Returns
    /// * On success: The generated completion text
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn completion(&self, request: CompletionRequest) -> crate::Result<Completion>;
}

/// Trait for models that generate text embeddings.
///
/// Implement this trait to create custom embedding model backends.
/// Use with [`crate::route::Router::<EmbeddingTag>`] for request routing.
///
/// # Example
///
/// ```ignore
/// #[thryd::async_trait]
/// impl EmbeddingModel for MyEmbeddingModel {
///     async fn embedding(&self, request: EmbeddingRequest) -> thryd::Result<Embeddings> {
///         // Call your embedding API
///         Ok(vec![vec![0.1, 0.2, 0.3]]) // Example embedding
///     }
/// }
/// ```
#[async_trait]
pub trait EmbeddingModel: Model {
    /// Generate embeddings for the given texts.
    ///
    /// # Arguments
    /// * `request` - The embedding request containing texts to encode
    ///
    /// # Returns
    /// * On success: Vector of embedding vectors, one per input text
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<Embeddings>;
}

/// Trait for models that rerank documents against a query.
///
/// Implement this trait to create custom reranker backends.
/// Use with [`crate::route::Router::<RerankerTag>`] for request routing.
///
/// # Example
///
/// ```ignore
/// #[thryd::async_trait]
/// impl RerankerModel for MyReranker {
///     async fn rerank(&self, request: RerankerRequest) -> thryd::Result<Ranking> {
///         // Compute relevance scores and return ranked indices
///         Ok(vec![(2, 0.95), (0, 0.80), (1, 0.30)])
///     }
/// }
/// ```
#[async_trait]
pub trait RerankerModel: Model {
    /// Rerank documents by relevance to the query.
    ///
    /// # Arguments
    /// * `request` - The reranker request with query and candidate documents
    ///
    /// # Returns
    /// * On success: Vector of `(document_index, score)` pairs, sorted by score descending
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn rerank(&self, request: RerankerRequest) -> crate::Result<Ranking>;
}
