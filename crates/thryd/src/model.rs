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
//! ## Response Types
//!
//! - [`CompletionResponse`] - Completion text with usage tracking
//! - [`EmbeddingResponse`] - Embedding vectors with usage tracking
//! - [`RankingResponse`] - Ranked document indices with usage tracking
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
pub use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Token usage reported by the API for a completed request.
///
/// Returned alongside every response so the router can track actual consumption
/// for rate limiting instead of estimating from text length.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Usage {
    /// Tokens consumed by the input prompt (text + images).
    pub prompt_tokens: u32,
    /// Tokens generated in the completion. Zero for embeddings and rerankers.
    pub completion_tokens: u32,
    /// Total tokens for this request (`prompt_tokens + completion_tokens`).
    pub total_tokens: u32,
}

/// Request payload for generating text embeddings.
///
/// Contains a batch of texts to encode into vector representations.
/// Use with [`EmbeddingModel`] implementations.
///
/// # Example
///
/// ```rust
/// use thryd::EmbeddingRequest;
///
/// let request = EmbeddingRequest {
///     texts: vec![
///         "The quick brown fox".to_string(),
///         "jumps over the lazy dog".to_string(),
///     ],
///     ndim: 1536,
///     max_batch_emb_size: None,
/// };
#[derive(Debug, Clone, Serialize)]
pub struct EmbeddingRequest {
    /// The batch of text strings to encode into embeddings.
    /// Each string is encoded as a separate embedding vector.
    pub texts: Vec<String>,
    pub ndim: u32,
    /// Maximum texts per batch. When set and `texts.len()` exceeds this,
    /// the model splits into chunks and fans out API calls, then merges results.
    /// Sub-requests carry `None` to prevent recursive splitting.
    #[serde(skip)]
    pub max_batch_emb_size: Option<usize>,
}

/// One image attached to a completion request.
///
/// The data URI is what the provider receives — possibly a compressed re-encode —
/// while the digest identifies the ORIGINAL bytes and is what the completion cache
/// keys on, so changing compression settings never changes cache hits.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImageAttachment {
    /// Payload sent to the provider, as a base64 data URI (`data:<mime>;base64,...`).
    pub uri: String,

    /// Hex blake3 of the original bytes, taken before any compression.
    pub digest: String,
}

/// Request payload for generating text completions.
///
/// Controls generation parameters like temperature, top_p, and token limits.
/// Use with [`CompletionModel`] implementations.
///
/// # Example
///
/// ```rust
/// use thryd::CompletionRequest;
///
/// let request = CompletionRequest {
///     message: "Explain recursion in programming".to_string(),
///     stream: false,
///     top_p: Some(0.9),
///     temperature: Some(0.7),
///     max_completion_tokens: Some(500),
///     ..Default::default()
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

    /// Images attached to the request, each carrying the data URI sent to the
    /// provider plus the digest of the original bytes the cache keys on.
    /// When non-empty, the OpenAI model builds multipart content internally.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    #[serde(default)]
    pub images: Vec<ImageAttachment>,

    /// Reasoning effort for models that support it (e.g. o1, o3).
    /// Must be one of `"low"`, `"medium"`, `"high"`, `"xhigh"`, `"minimal"`, or `None`.
    /// Non-standard strings (e.g. `"ultra"`) are forwarded verbatim to compatible providers.
    /// `None` uses provider default.
    pub effort: Option<String>,
}

/// Request payload for reranking documents against a query.
///
/// Takes a query and list of candidate documents, returns them ranked by relevance.
/// Use with [`RerankerModel`] implementations.
///
/// # Example
///
/// ```rust
/// use thryd::RerankerRequest;
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
/// Trait for response types that carry API-reported token usage.
///
/// Implemented by the completion, embedding, ranking, and evaluation responses. Enables generic
/// usage extraction without tuple `.1` destructuring.
pub trait WithUsage {
    /// Returns the API-reported usage, if available.
    ///
    /// Owned rather than borrowed: a response may report what it cost in its own shape — the
    /// evaluation API, for instance, counts input and output tokens in its own type — and the
    /// router's [`Usage`] is then built on the way out.
    fn usage(&self) -> Option<Usage>;
}

/// Type alias for a single embedding vector.
pub type Embedding = Vec<f32>;

/// Type alias for completion text content (just the string, no usage).
pub type CompletionText = String;

/// Type alias for ranked document output (index, score pairs).
pub type RankedDocuments = Vec<(usize, f32)>;

/// Completion response with usage tracking.
///
/// Contains the generated text and API-reported token consumption.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CompletionResponse {
    pub content: CompletionText,
    pub usage: Usage,
}

impl WithUsage for CompletionResponse {
    fn usage(&self) -> Option<Usage> {
        Some(self.usage.clone())
    }
}

/// Embedding response with usage tracking.
///
/// Contains embedding vectors and API-reported token consumption.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EmbeddingResponse {
    pub embeddings: Vec<Embedding>,
    pub usage: Usage,
}

impl WithUsage for EmbeddingResponse {
    fn usage(&self) -> Option<Usage> {
        Some(self.usage.clone())
    }
}

/// Ranking response with usage tracking.
///
/// Contains ranked document indices with relevance scores and API-reported token consumption.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RankingResponse {
    pub rankings: RankedDocuments,
    pub usage: Usage,
}

impl WithUsage for RankingResponse {
    fn usage(&self) -> Option<Usage> {
        Some(self.usage.clone())
    }
}
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
///     async fn completion(&self, request: CompletionRequest) -> thryd::Result<CompletionResponse> {
///         Ok(CompletionResponse {
///             content: "Generated text response".to_string(),
///             usage: Usage::default(),
///         })
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
    /// * On success: A [`CompletionResponse`] with the generated text and usage
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn completion(&self, request: CompletionRequest) -> crate::Result<CompletionResponse>;
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
///     async fn embedding(&self, request: EmbeddingRequest) -> thryd::Result<EmbeddingResponse> {
///         Ok(EmbeddingResponse {
///             embeddings: vec![vec![0.1, 0.2, 0.3]],
///             usage: Usage::default(),
///         })
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
    /// * On success: An [`EmbeddingResponse`] with vectors and usage
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<EmbeddingResponse>;
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
///     async fn rerank(&self, request: RerankerRequest) -> thryd::Result<RankingResponse> {
///         Ok(RankingResponse {
///             rankings: vec![(2, 0.95), (0, 0.80), (1, 0.30)],
///             usage: Usage::default(),
///         })
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
    /// * On success: A [`RankingResponse`] with ranked indices and usage
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn rerank(&self, request: RerankerRequest) -> crate::Result<RankingResponse>;
}

/// Request payload for evaluating a state against named questions.
///
/// An evaluation is not a conversation: one state — text, or structured JSON such as a chat log or
/// a record — is checked against a set of questions in a single call, and every question is
/// answered with a probability. The types are [`jevlin`]'s, so a caller that declares a question
/// set once (a struct of answers with `#[derive(Answers)]`) asks the same declaration here, and
/// reads the answers back into it with [`read`](jevlin::Response::read).
///
/// The request carries the model that answers it. A request that still holds the moving
/// [`jev-latest`](jevlin::Model::LATEST_ALIAS) alias takes the deployment's model name instead, so
/// the deployment id pins the version for every call that does not pin one itself.
#[cfg(feature = "jev")]
pub use jevlin::{
    Answer as EvaluationAnswer, Model as EvaluationModelName, Question as EvaluationQuestion,
    Request as EvaluationRequest, Response as EvaluationResponse, State as EvaluationState,
};

/// Trait for models that evaluate a state against a set of typed questions.
///
/// Implement this trait to create custom evaluation backends. Use with
/// [`crate::route::Router::<EvaluationTag>`], where one deployment answers a whole question set in
/// one call and the router caches the answers under the state and the questions that produced them.
///
/// # Example
///
/// ```ignore
/// #[thryd::async_trait]
/// impl EvaluationModel for MyEvaluator {
///     async fn evaluate(&self, request: EvaluationRequest) -> thryd::Result<EvaluationResponse> {
///         // Custom implementation
///         unimplemented!()
///     }
/// }
/// ```
#[cfg(feature = "jev")]
#[async_trait]
pub trait EvaluationModel: Model {
    /// Evaluates every question of `request` against its state, in one call.
    ///
    /// # Arguments
    /// * `request` - The state to evaluate, and the questions to ask about it
    ///
    /// # Returns
    /// * On success: An [`EvaluationResponse`] holding one answer per question, the model that
    ///   gave them, and what they cost
    /// * On error: A [`crate::ThrydError`] indicating the failure reason
    async fn evaluate(&self, request: EvaluationRequest) -> crate::Result<EvaluationResponse>;
}

/// Maps the evaluation client's token counts onto the router's usage fields.
///
/// The API reports the tokens the model read and wrote; the router additionally tracks their sum,
/// so a response carries everything rate limiting and reporting need.
#[cfg(feature = "jev")]
impl From<jevlin::Usage> for Usage {
    fn from(usage: jevlin::Usage) -> Self {
        let prompt_tokens = u32::try_from(usage.input_tokens).unwrap_or(u32::MAX);
        let completion_tokens = u32::try_from(usage.output_tokens).unwrap_or(u32::MAX);
        Self {
            prompt_tokens,
            completion_tokens,
            total_tokens: prompt_tokens.saturating_add(completion_tokens),
        }
    }
}

#[cfg(feature = "jev")]
impl WithUsage for EvaluationResponse {
    fn usage(&self) -> Option<Usage> {
        Some(self.usage.into())
    }
}
