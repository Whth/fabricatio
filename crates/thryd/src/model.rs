use async_trait::async_trait;

pub struct EmbeddingRequest {
    pub input: Vec<String>,
}

pub struct CompletionRequest {
    pub input: String,
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