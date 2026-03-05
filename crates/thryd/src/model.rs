use async_trait::async_trait;
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct EmbeddingRequest {
    pub texts: Vec<String>,
}


#[derive(Debug, Clone, Serialize)]
pub struct CompletionRequest {
    pub message: String,
    pub model: String,
    pub top_p: f32,
    pub temperature: f32,
}


pub trait Model: Send + Sync {
    fn model_name(&self) -> &str;
}

#[async_trait]
pub trait CompletionModel: Model {
    async fn completion(&self, request: CompletionRequest) -> crate::Result<String>;
}


#[async_trait]
pub trait EmbeddingModel: Model {
    async fn embedding(&self, request: EmbeddingRequest) -> crate::Result<Vec<f32>>;
}