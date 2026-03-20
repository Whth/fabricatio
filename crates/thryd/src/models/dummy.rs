use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use crate::provider::dummy::DummyProvider;
use async_trait::async_trait;
use std::sync::{Arc, Mutex};

pub struct DummyModel {
    name: String,
    response_q_string: Mutex<Vec<String>>,
    response_q_vec: Mutex<Vec<Vec<Vec<f32>>>>,
    provider: Arc<dyn Provider>,
}

impl DummyModel {
    pub fn new(name: String, provider: Arc<dyn Provider>) -> Self {
        Self {
            name,
            response_q_string: Mutex::new(vec![]),
            response_q_vec: Mutex::new(vec![]),
            provider,
        }
    }

    pub fn with_completion_responses(self, responses: Vec<String>) -> Self {
        *self.response_q_string.lock().unwrap() = responses;
        self
    }

    pub fn with_embedding_responses(self, responses: Vec<Vec<Vec<f32>>>) -> Self {
        *self.response_q_vec.lock().unwrap() = responses;
        self
    }
}

impl Default for DummyModel {
    fn default() -> Self {
        Self::new("dummy".to_string(), Arc::new(DummyProvider::default()))
    }
}

impl Model for DummyModel {
    fn model_name(&self) -> &str {
        &self.name
    }

    fn provider(&self) -> Arc<dyn Provider> {
        todo!()
    }
}

#[async_trait]
impl CompletionModel for DummyModel {
    async fn completion(&self, _request: CompletionRequest) -> crate::Result<String> {
        let mut queue = self
            .response_q_string
            .lock()
            .map_err(|e| crate::ThrydError::Internal(e.to_string()))?;

        queue.pop().ok_or_else(|| {
            crate::ThrydError::Internal(
                "DummyModel exhausted: no more completion responses configured.".to_string(),
            )
        })
    }
}

#[async_trait]
impl EmbeddingModel for DummyModel {
    async fn embedding(&self, _request: EmbeddingRequest) -> crate::Result<Vec<Vec<f32>>> {
        let mut queue = self
            .response_q_vec
            .lock()
            .map_err(|e| crate::ThrydError::Internal(e.to_string()))?;

        queue.pop().ok_or_else(|| {
            crate::ThrydError::Internal(
                "DummyModel exhausted: no more embedding responses configured.".to_string(),
            )
        })
    }
}
