use crate::SEPARATE;
use crate::provider::Provider;
use async_trait::async_trait;
use serde::Serialize;
use std::sync::Arc;

#[derive(Debug, Clone, Serialize)]
pub struct EmbeddingRequest {
    pub texts: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompletionRequest {
    pub message: String,
    pub top_p: f32,
    pub temperature: f32,
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
