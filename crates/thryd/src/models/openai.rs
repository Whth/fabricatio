use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use async_trait::async_trait;
use std::sync::Arc;

struct OpenaiModel {
    name: String,
    provider: Arc<dyn Provider>,
}

impl Model for OpenaiModel {
    fn model_name(&self) -> &str {
        self.name.as_str()
    }
}

#[async_trait]
impl CompletionModel for OpenaiModel {
    async fn completion(&self, _request: CompletionRequest) -> crate::Result<String> {
        todo!()
    }
}


#[async_trait]
impl EmbeddingModel for OpenaiModel {
    async fn embedding(&self, _request: EmbeddingRequest) -> crate::Result<Vec<f32>> {
        todo!()
    }
}





