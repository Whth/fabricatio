use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use async_openai::types::chat::{
    ChatCompletionRequestUserMessageArgs, CreateChatCompletionRequest,
    CreateChatCompletionRequestArgs, CreateChatCompletionResponse,
    CreateChatCompletionStreamResponse,
};

use crate::ThrydError;
use async_openai::types::embeddings::{CreateEmbeddingRequestArgs, CreateEmbeddingResponse};
use async_trait::async_trait;
use eventsource_stream::Eventsource;
use futures::{StreamExt, TryStreamExt};
use serde_json::to_value;
use std::sync::Arc;
use strum::{AsRefStr, Display, EnumString};
use strum_macros::EnumIter;
use tracing::{debug, trace};

/// Represents all standard OpenAI API v1 endpoints.
///
/// This enum uses `strum` to safely map Rust variants to exact URL paths required by OpenAI.
/// It prevents typos in critical API paths and centralizes route management.
///
/// # Features
/// - `Display`: Convert to String (allocates).
/// - `AsRefStr`: Convert to &str (zero-copy, recommended for network calls).
/// - `EnumString`: Parse from string (useful for config files).
/// - `IntoEnumIterator`: Iterate over all available endpoints.
#[derive(Debug, Clone, Copy, Display, AsRefStr, EnumString, EnumIter)]
pub enum OpenAiRoute {
    /// Chat Completions API: `chat/completions`
    /// Used for GPT-3.5, GPT-4, and other chat models.
    #[strum(serialize = "chat/completions")]
    ChatCompletions,

    /// Legacy Completions API: `completions`
    /// Used for older base models (e.g., davinci, curie). Note: Deprecated for newer models.
    #[strum(serialize = "completions")]
    Completions,

    /// Models List: `models`
    /// Lists the currently available models.
    #[strum(serialize = "models")]
    ListModels,

    /// Embeddings API: `embeddings`
    /// Generates embeddings for text inputs.
    #[strum(serialize = "embeddings")]
    Embeddings,
}
pub struct OpenaiModel {
    name: String,
    provider: Arc<dyn Provider>,
}

impl OpenaiModel {
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

#[async_trait]
impl CompletionModel for OpenaiModel {
    async fn completion(&self, request: CompletionRequest) -> crate::Result<String> {
        let stream = request.stream;
        let request = CreateChatCompletionRequest {
            top_p: request.top_p,
            temperature: request.temperature,
            max_completion_tokens: request.max_completion_tokens,
            presence_penalty: request.presence_penalty,
            frequency_penalty: request.frequency_penalty,
            ..CreateChatCompletionRequestArgs::default()
                .model(self.model_name())
                .stream(request.stream)
                .messages([ChatCompletionRequestUserMessageArgs::default()
                    .content(request.message)
                    .build()?
                    .into()])
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
                .await?
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

#[async_trait]
impl EmbeddingModel for OpenaiModel {
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<Vec<Vec<f32>>> {
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
            .collect::<Vec<Vec<f32>>>())
    }
}
