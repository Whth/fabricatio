use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use async_trait::async_trait;
use std::sync::Mutex;

pub struct DummyModel {
    name: String,
    response_q_string: Mutex<Vec<String>>,
    response_q_vec: Mutex<Vec<Vec<f32>>>,
}

impl DummyModel {
    pub fn new(name: String) -> Self {
        Self {
            name,
            response_q_string: Mutex::new(vec![]),
            response_q_vec: Mutex::new(vec![]),
        }
    }

    pub fn with_completion_responses(self, responses: Vec<String>) -> Self {
        *self.response_q_string.lock().unwrap() = responses;
        self
    }

    pub fn with_embedding_responses(self, responses: Vec<Vec<f32>>) -> Self {
        *self.response_q_vec.lock().unwrap() = responses;
        self
    }
}

impl Default for DummyModel {
    fn default() -> Self {
        Self::new("dummy".to_string())
    }
}

impl Model for DummyModel {
    fn model_name(&self) -> &str {
        &self.name
    }
}

#[async_trait]
impl CompletionModel for DummyModel {
    async fn completion(&self, _request: CompletionRequest) -> crate::Result<String> {
        let mut queue = self.response_q_string.lock().map_err(|e| crate::ThrydError::Internal(e.to_string()))?;

        queue.pop()
            .ok_or_else(|| crate::ThrydError::Internal("DummyModel exhausted: no more completion responses configured.".to_string()))
    }
}

#[async_trait]
impl EmbeddingModel for DummyModel {
    async fn embedding(&self, _request: EmbeddingRequest) -> crate::Result<Vec<f32>> {
        let mut queue = self.response_q_vec.lock().map_err(|e| crate::ThrydError::Internal(e.to_string()))?;

        queue.pop()
            .ok_or_else(|| crate::ThrydError::Internal("DummyModel exhausted: no more embedding responses configured.".to_string()))
    }
}


mod tests {
    use super::*;
    #[tokio::test]
    async fn test_dummy_model_default() {
        let model = DummyModel::default();
        assert_eq!(model.model_name(), "dummy");
    }

    #[tokio::test]
    async fn test_dummy_model_with_name() {
        let model = DummyModel::new("custom_model".to_string());
        assert_eq!(model.model_name(), "custom_model");
    }

    #[tokio::test]
    async fn test_completion_model_success() {
        let responses = vec!["response1".to_string(), "response2".to_string()];
        let model = DummyModel::default().with_completion_responses(responses);

        let request = CompletionRequest {
            message: "test prompt".to_string(),
            model: "".to_string(),
            top_p: 0.0,
            temperature: 0.0,
        };

        let result1 = model.completion(request.clone()).await;
        assert!(result1.is_ok());
        assert_eq!(result1.unwrap(), "response2");

        let result2 = model.completion(request).await;
        assert!(result2.is_ok());
        assert_eq!(result2.unwrap(), "response1");
    }

    #[tokio::test]
    async fn test_completion_model_exhausted() {
        let model = DummyModel::default();

        let request = CompletionRequest {
            message: "test prompt".to_string(),
            model: "".to_string(),
            top_p: 0.0,
            temperature: 0.0,
        };

        let result = model.completion(request).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("exhausted"));
    }

    #[tokio::test]
    async fn test_embedding_model_success() {
        let responses = vec![
            vec![1.0, 2.0, 3.0],
            vec![4.0, 5.0, 6.0],
        ];
        let model = DummyModel::default().with_embedding_responses(responses);

        let request = EmbeddingRequest {
            texts: vec!["test text".to_string()],
        };

        let result1 = model.embedding(request.clone()).await;
        assert!(result1.is_ok());
        assert_eq!(result1.unwrap(), vec![4.0, 5.0, 6.0]);

        let result2 = model.embedding(request).await;
        assert!(result2.is_ok());
        assert_eq!(result2.unwrap(), vec![1.0, 2.0, 3.0]);
    }

    #[tokio::test]
    async fn test_embedding_model_exhausted() {
        let model = DummyModel::default();

        let request = EmbeddingRequest {
            texts: vec!["test text".to_string()],

        };

        let result = model.embedding(request).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("exhausted"));
    }

    #[tokio::test]
    async fn test_mixed_usage() {
        let completion_responses = vec!["completion_response".to_string()];
        let embedding_responses = vec![vec![1.0, 2.0, 3.0]];

        let model = DummyModel::new("mixed_model".to_string())
            .with_completion_responses(completion_responses)
            .with_embedding_responses(embedding_responses);

        // Test completion
        let completion_request = CompletionRequest {
            message: "test".to_string(),
            model: "".to_string(),
            top_p: 0.0,
            temperature: 0.0,
        };
        let completion_result = model.completion(completion_request).await;
        assert!(completion_result.is_ok());
        assert_eq!(completion_result.unwrap(), "completion_response");

        // Test embedding
        let embedding_request = EmbeddingRequest {
            texts: vec!["test".to_string()],
        };
        let embedding_result = model.embedding(embedding_request).await;
        assert!(embedding_result.is_ok());
        assert_eq!(embedding_result.unwrap(), vec![1.0, 2.0, 3.0]);

        // Verify both queues are now empty
        let completion_request2 = CompletionRequest {
            message: "test2".to_string(),
            model: "".to_string(),
            top_p: 0.0,
            temperature: 0.0,
        };
        let completion_result2 = model.completion(completion_request2).await;
        assert!(completion_result2.is_err());

        let embedding_request2 = EmbeddingRequest {
            texts: vec!["test2".to_string()],
        };
        let embedding_result2 = model.embedding(embedding_request2).await;
        assert!(embedding_result2.is_err());
    }
}


