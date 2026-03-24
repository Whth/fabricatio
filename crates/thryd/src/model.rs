use crate::SEPARATE;
use crate::provider::Provider;
use async_trait::async_trait;
use serde::Serialize;
use std::sync::Arc;

#[derive(Debug, Clone, Serialize)]
pub struct EmbeddingRequest {
    pub texts: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct CompletionRequest {
    pub message: String,
    pub stream: bool,
    pub top_p: Option<f32>,
    pub temperature: Option<f32>,
    pub max_completion_tokens: Option<u32>,
    pub presence_penalty: Option<f32>,
    pub frequency_penalty: Option<f32>,
}

pub trait Model: Send + Sync {
    fn model_name(&self) -> &str;

    fn provider(&self) -> Arc<dyn Provider>;

    fn identifier(&self) -> String {
        format!(
            "{}{SEPARATE}{}",
            self.provider().provider_name(),
            self.model_name()
        )
    }
}

#[async_trait]
pub trait CompletionModel: Model {
    async fn completion(&self, request: CompletionRequest) -> crate::Result<String>;
}

#[async_trait]
pub trait EmbeddingModel: Model {
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<Vec<Vec<f32>>>;
}
