use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::tracker::count_token;
use crate::Result;
use crate::UsageTracker;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};


pub struct Deployment<M: ?Sized + Model> {
    model: Box<M>,
    usage_tracker: Option<Mutex<UsageTracker>>,
}

impl<M: ?Sized + Model> Deployment<M> {
    pub fn new(model: Box<M>) -> Deployment<M>
    {
        Self {
            model,
            usage_tracker: None,
        }
    }

    pub fn identifier(&self) -> String {
        self.model.identifier()
    }


    pub fn with_usage_constrain(mut self, rpm: Option<u32>, tpm: Option<u32>) -> Self {
        self.usage_tracker = Some(Mutex::new(UsageTracker::with_quota(tpm, rpm)));
        self
    }

    pub async fn is_ready(&self) -> bool {
        if let Some(tracker) = &self.usage_tracker {
            tracker.lock().await.has_capacity()
        } else {
            true
        }
    }

    pub async fn wait_capacity_for(&self, input_text: String) -> Result<&Self> {
        if let Some(tracker) = &self.usage_tracker {
            let need = count_token(input_text);
            while let time = tracker.lock().await.estimated_waiting_time_for_tokens(need) && time > 0 {
                sleep(Duration::from_millis(time)).await;
            }
            Ok(self)
        } else {
            Ok(self)
        }
    }


    pub async fn completion(&self, request: CompletionRequest) -> Result<String>
    where
        M: CompletionModel,
    {
        let input = request.message.to_string();
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
        let input = request.texts.iter().cloned().collect();
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










