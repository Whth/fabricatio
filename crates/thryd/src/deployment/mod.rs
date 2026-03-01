use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::Result;
use crate::UsageTracker;
use tokio::sync::Mutex;
pub struct Deployment<M: ?Sized + Model> {
    model: Box<M>,
    usage_tracker: Option<Mutex<UsageTracker>>,
}

impl<M: ?Sized + Model> Deployment<M> {
    pub fn new(model: M) -> Deployment<M>
    where
        M: Sized,
    {
        Self {
            model: Box::new(model),
            usage_tracker: None,
        }
    }

    pub fn with_usage_constrain(mut self, rpm: Option<u32>, tpm: Option<u32>) -> Self {
        self.usage_tracker = Some(Mutex::new(UsageTracker::with_quota(tpm, rpm)));
        self
    }

    pub async fn is_ready_for(&self) -> bool {
        if let Some(tracker) = &self.usage_tracker {
            tracker.lock().await.has_capacity()
        } else {
            true
        }
    }


    pub async fn completion(&self, request: CompletionRequest) -> Result<String>
    where
        M: CompletionModel,
    {
        let input = request.input.to_string();
        let res = self.model.completion(request).await;
        if let Some(tracker) = &self.usage_tracker && let Ok(r) = &res {
            tracker
                .lock()
                .await
                .add_request_raw(input, r.to_string());
        }

        res
    }


    pub async fn embedding(&self, request: EmbeddingRequest) -> Result<Vec<f32>>
    where
        M: EmbeddingModel,
    {
        let input = request.input.iter().cloned().collect();
        let res = self.model.embedding(request).await;
        if let Some(tracker) = &self.usage_tracker && res.is_ok() {
            tracker
                .lock()
                .await
                .add_request_raw(input, "".to_string());
        }

        res
    }
}










