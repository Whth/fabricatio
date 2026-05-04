//! OpenAI API model implementation.
//!
//! This module provides the [`OpenaiModel`] implementation for interacting with
//! OpenAI-compatible APIs using the standard REST endpoints.
//!
//! # Example
//!
//! ```ignore
//! use thryd::{OpenaiModel, OpenaiCompatible, CompletionRequest};
//! use secrecy::SecretString;
//! use std::sync::Arc;
//!
//! let api_key = SecretString::from("sk-...".to_string());
//! let provider = Arc::new(OpenaiCompatible::openai(api_key));
//! let model = OpenaiModel::new("gpt-4".to_string(), provider);
//!
//! let response = model.completion(CompletionRequest {
//!     message: "Hello, world!".to_string(),
//!     top_p: 0.9,
//!     temperature: 0.7,
//!     stream: false,
//!     max_completion_tokens: 100,
//!     presence_penalty: 0.0,
//!     frequency_penalty: 0.0,
//! }).await?;
//! ```

use crate::model::{
    CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model,
};
use crate::provider::Provider;
use async_openai::types::chat::{
    ChatCompletionRequestUserMessageArgs, CreateChatCompletionRequest,
    CreateChatCompletionRequestArgs, CreateChatCompletionResponse,
    CreateChatCompletionStreamResponse,
};

use crate::{Completion, Embeddings, ThrydError};
use async_openai::types::embeddings::{CreateEmbeddingRequestArgs, CreateEmbeddingResponse};
use async_trait::async_trait;
use eventsource_stream::Eventsource;
use futures::{StreamExt, TryStreamExt};
use serde_json::to_value;
use std::sync::Arc;
use strum::{AsRefStr, Display, EnumString};
use strum_macros::EnumIter;
use tracing::*;

/// Represents all standard OpenAI API v1 endpoints.
///
/// This enum uses `strum` to safely map Rust variants to exact URL paths required by OpenAI.
/// It prevents typos in critical API paths and centralizes route management.
///
/// # Variants
///
/// - [`ChatCompletions`](OpenAiRoute::ChatCompletions) - Chat completions API for GPT-3.5, GPT-4, etc.
/// - [`Completions`](OpenAiRoute::Completions) - Legacy completions API for base models
/// - [`ListModels`](OpenAiRoute::ListModels) - List available models
/// - [`Embeddings`](OpenAiRoute::Embeddings) - Generate text embeddings
///
/// # Traits Enabled
///
/// - [`Debug`](std::fmt::Debug) - For debug formatting
/// - [`Clone`] - Can be copied
/// - [`Display`] - Convert to `String` (allocates)
/// - [`AsRefStr`] - Convert to `&str` (zero-copy, recommended)
/// - [`EnumString`] - Parse from string (useful for config)
/// - [`EnumIter`] - Iterate over all variants
///
/// # Example
///
/// ```ignore
/// use thryd::models::openai::OpenAiRoute;
///
/// // Using as_ref() for zero-copy string access
/// let path = OpenAiRoute::Embeddings.as_ref();
/// assert_eq!(path, "embeddings");
///
/// // Parse from string
/// let route: OpenAiRoute = "chat/completions".parse().unwrap();
/// ```
#[derive(Debug, Clone, Copy, Display, AsRefStr, EnumString, EnumIter)]
pub enum OpenAiRoute {
    /// Chat Completions API: `chat/completions`
    ///
    /// Used for GPT-3.5, GPT-4, and other chat models. This is the primary
    /// endpoint for modern OpenAI language models.
    ///
    /// # API Path
    /// `POST /v1/chat/completions`
    #[strum(serialize = "chat/completions")]
    ChatCompletions,

    /// Legacy Completions API: `completions`
    ///
    /// Used for older base models such as `davinci`, `curie`, `ada`, and `babbage`.
    /// Note: This endpoint is deprecated for newer models in favor of chat completions.
    ///
    /// # API Path
    /// `POST /v1/completions`
    #[strum(serialize = "completions")]
    Completions,

    /// Models List: `models`
    ///
    /// Returns a list of all available models accessible by the API key.
    ///
    /// # API Path
    /// `GET /v1/models`
    #[strum(serialize = "models")]
    ListModels,

    /// Embeddings API: `embeddings`
    ///
    /// Generates vector embeddings for text inputs. Used for semantic search,
    /// similarity comparisons, and as input for RAG systems.
    ///
    /// # API Path
    /// `POST /v1/embeddings`
    #[strum(serialize = "embeddings")]
    Embeddings,
}

/// OpenAI-compatible model implementation.
///
/// This struct wraps a model name and a provider, exposing completion and embedding
/// capabilities through the standard OpenAI API format.
///
/// # Type Parameters
///
/// - `provider: Arc<dyn Provider>` - Must be an OpenAI-compatible API provider
///
/// # Example
///
/// ```ignore
/// use thryd::{OpenaiModel, OpenaiCompatible, CompletionRequest, EmbeddingRequest};
/// use secrecy::SecretString;
/// use std::sync::Arc;
///
/// let api_key = SecretString::from("sk-...".to_string());
/// let provider = Arc::new(OpenaiCompatible::openai(api_key));
///
/// // Create a chat completion model
/// let gpt4 = OpenaiModel::new("gpt-4".to_string(), provider.clone());
///
/// // Create an embedding model
/// let ada = OpenaiModel::new("text-embedding-3-small".to_string(), provider);
/// ```
pub struct OpenaiModel {
    /// The model name/identifier (e.g., "gpt-4", "text-embedding-3-small")
    name: String,
    /// The OpenAI-compatible provider to make requests through
    provider: Arc<dyn Provider>,
}

impl OpenaiModel {
    /// Creates a new `OpenaiModel` with the specified name and provider.
    ///
    /// # Arguments
    ///
    /// * `name` - The model identifier (e.g., "gpt-4", "gpt-3.5-turbo", "text-embedding-3-small")
    /// * `provider` - An OpenAI-compatible provider instance
    ///
    /// # Example
    ///
    /// ```ignore
    /// use thryd::{OpenaiModel, OpenaiCompatible};
    /// use secrecy::SecretString;
    /// use std::sync::Arc;
    ///
    /// let api_key = SecretString::from("sk-...".to_string());
    /// let provider = Arc::new(OpenaiCompatible::openai(api_key));
    ///
    /// let model = OpenaiModel::new("gpt-4".to_string(), provider);
    /// ```
    pub fn new(name: String, provider: Arc<dyn Provider>) -> Self {
        Self { name, provider }
    }
}

impl Model for OpenaiModel {
    fn model_name(&self) -> &str {
        self.name.as_str()
    }

    fn provider(&self) -> Arc<dyn Provider> {
        self.provider.clone()
    }
}

/// # Completion Implementation
///
/// Implements [`CompletionModel`] for `OpenaiModel`, providing text generation
/// capabilities through the OpenAI Chat Completions API.
///
/// ## Streaming vs Non-Streaming
///
/// The completion request supports two modes based on the `stream` field:
///
/// - **Non-Streaming (`stream: false`)**: Waits for the complete response,
///   then returns it as a single `String`. The response includes token usage
///   statistics logged at the `debug` level.
///
/// - **Streaming (`stream: true`)**: Returns an `Iterator` of content chunks
///   as they arrive from the server. Each chunk is a `String` containing a
///   partial response delta. This is useful for real-time displays like
///   chatbots or terminal applications.
///
/// # Example
///
/// ```ignore
/// use thryd::{OpenaiModel, OpenaiCompatible, CompletionRequest};
/// use secrecy::SecretString;
/// use std::sync::Arc;
///
/// let provider = Arc::new(OpenaiCompatible::openai(api_key));
/// let model = OpenaiModel::new("gpt-4".to_string(), provider);
///
/// // Non-streaming completion
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
/// let response = model.completion(request).await?;
/// println!("Response: {}", response);
///
/// // Streaming completion (returns iterator of chunks)
/// let streaming_request = CompletionRequest {
///     message: "Count to 5:".to_string(),
///     stream: true,
///     ..Default::default()
/// };
/// for chunk in model.completion(streaming_request).await? {
///     print!("{}", chunk);
/// }
/// println!();
/// ```
///
/// [`CompletionModel`]: crate::model::CompletionModel
#[async_trait]
impl CompletionModel for OpenaiModel {
    async fn completion(&self, request: CompletionRequest) -> crate::Result<Completion> {
        use async_openai::types::chat::ChatCompletionRequestSystemMessageArgs;

        let stream = request.stream;

        // Build messages list: history + current message
        let mut messages = Vec::with_capacity(request.history.len() + 1);

        // Add history messages
        for msg in &request.history {
            match msg.role.as_str() {
                "system" => {
                    messages.push(
                        ChatCompletionRequestSystemMessageArgs::default()
                            .content(msg.content.as_str())
                            .build()
                            .unwrap()
                            .into(),
                    );
                }
                "user" => {
                    messages.push(
                        ChatCompletionRequestUserMessageArgs::default()
                            .content(msg.content.as_str())
                            .build()
                            .unwrap()
                            .into(),
                    );
                }
                _ => {
                    // Treat unknown roles as user messages for compatibility
                    messages.push(
                        ChatCompletionRequestUserMessageArgs::default()
                            .content(msg.content.as_str())
                            .build()
                            .unwrap()
                            .into(),
                    );
                }
            }
        }

        // Add current message
        messages.push(
            ChatCompletionRequestUserMessageArgs::default()
                .content(request.message.as_str())
                .build()
                .unwrap()
                .into(),
        );

        let request = CreateChatCompletionRequest {
            top_p: request.top_p,
            temperature: request.temperature,
            max_completion_tokens: request.max_completion_tokens,
            presence_penalty: request.presence_penalty,
            frequency_penalty: request.frequency_penalty,
            ..CreateChatCompletionRequestArgs::default()
                .model(self.model_name())
                .stream(stream)
                .messages(messages)
                .build()?
        };

        let v = to_value(request)?;
        trace!("Completion request: {v:?}",);
        if stream {
            let res = self
                .provider
                .post(OpenAiRoute::ChatCompletions.as_ref(), &v)
                .await?
                .error_for_status()?
                .bytes_stream()
                .eventsource()
                .map(|event| {
                    serde_json::from_str::<CreateChatCompletionStreamResponse>(event?.data.as_str())
                        .map_err(ThrydError::from)
                })
                .try_collect::<Vec<CreateChatCompletionStreamResponse>>()
                .await?
                .into_iter()
                .map(|resp| {
                    resp.choices
                        .first()
                        .cloned()
                        .unwrap()
                        .delta
                        .content
                        .unwrap()
                        .clone()
                })
                .collect();
            Ok(res)
        } else {
            let content = if let Some(choice) = self
                .provider
                .post(OpenAiRoute::ChatCompletions.as_ref(), &v)
                .await?
                .error_for_status()?
                .json::<CreateChatCompletionResponse>()
                .await
                .inspect(|resp| {
                    if let Some(usage) = resp.usage.as_ref() {
                        debug!(
                            "Request tokens usages: Input {} | Output {} | Total {}",
                            usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
                        )
                    }
                })?
                .choices
                .first()
                && let Some(content) = choice.message.content.clone()
            {
                content
            } else {
                String::new()
            };
            Ok(content)
        }
    }
}

/// # Embedding Implementation
///
/// Implements [`EmbeddingModel`] for `OpenaiModel`, providing text vectorization
/// through the OpenAI Embeddings API.
///
/// Generates vector embeddings for a list of input texts. Embeddings are
/// returned as `Vec<Vec<f32>>` where each inner vector is the embedding
/// for the corresponding input text in order.
///
/// # Example
///
/// ```ignore
/// use thryd::{OpenaiModel, OpenaiCompatible, EmbeddingRequest};
/// use secrecy::SecretString;
/// use std::sync::Arc;
///
/// let provider = Arc::new(OpenaiCompatible::openai(api_key));
/// let model = OpenaiModel::new("text-embedding-3-small".to_string(), provider);
///
/// let request = EmbeddingRequest {
///     texts: vec![
///         "Hello, world!".to_string(),
///         "How are you?".to_string(),
///     ],
/// };
///
/// let embeddings = model.embedding(request).await?;
/// assert_eq!(embeddings.len(), 2); // Two embeddings for two texts
/// assert_eq!(embeddings[0].len(), 1536); // text-embedding-3-small uses 1536 dims
/// ```
///
/// [`EmbeddingModel`]: crate::model::EmbeddingModel
#[async_trait]
impl EmbeddingModel for OpenaiModel {
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<Embeddings> {
        let request = CreateEmbeddingRequestArgs::default()
            .model(self.model_name())
            .input(request.texts)
            .build()?;

        let v = to_value(request)?;
        Ok(self
            .provider
            .post(OpenAiRoute::Embeddings.as_ref(), &v)
            .await?
            .json::<CreateEmbeddingResponse>()
            .await?
            .data
            .into_iter()
            .map(|e| e.embedding)
            .collect::<Embeddings>())
    }
}
