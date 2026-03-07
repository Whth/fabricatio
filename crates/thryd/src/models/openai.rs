use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use async_openai::types::chat::{ChatCompletionRequestUserMessageArgs, CreateChatCompletionRequestArgs, CreateChatCompletionResponse};
use async_trait::async_trait;
use serde_json::to_value;
use std::sync::Arc;
use strum::{AsRefStr, Display, EnumString};
use strum_macros::EnumIter;

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
    /// Chat Completions API: `/v1/chat/completions`
    /// Used for GPT-3.5, GPT-4, and other chat models.
    #[strum(serialize = "/v1/chat/completions")]
    ChatCompletions,

    /// Legacy Completions API: `/v1/completions`
    /// Used for older base models (e.g., davinci, curie). Note: Deprecated for newer models.
    #[strum(serialize = "/v1/completions")]
    Completions,

    /// Models List: `/v1/models`
    /// Lists the currently available models.
    #[strum(serialize = "/v1/models")]
    ListModels,

    /// Embeddings API: `/v1/embeddings`
    /// Generates embeddings for text inputs.
    #[strum(serialize = "/v1/embeddings")]
    Embeddings,

}
struct OpenaiModel {
    name: String,
    provider: Arc<dyn Provider>,
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
        let request = CreateChatCompletionRequestArgs::default()
            .model(request.model) // Or "gpt-3.5-turbo", "gpt-4", etc.
            .messages([
                ChatCompletionRequestUserMessageArgs::default()
                    .content(request.message)
                    .build()?
                    .into(),
            ])
            .build()?;


        let content = if let Some(choice) = self.provider.post(OpenAiRoute::ChatCompletions.as_ref(), &to_value(request)?)
            .await?
            .json::<CreateChatCompletionResponse>()
            .await?
            .choices
            .first() && let Some(content) = choice.message.content.clone() {
            content
        } else {
            String::new()
        };


        Ok(content)
    }
}


#[async_trait]
impl EmbeddingModel for OpenaiModel {
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<Vec<f32>> {
        todo!()
    }
}





