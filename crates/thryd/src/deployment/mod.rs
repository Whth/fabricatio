use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::tracker::count_token;
use crate::{
    Completion, Embeddings, Ranking, RerankerModel, RerankerRequest, Result, UsageTracker,
};
use tokio::sync::Mutex;
use tokio::time::{Duration, sleep};

macro_rules! with_tracking {
    ($tracker:expr, $input:expr, $res:expr) => {{
        if $res.is_ok() {
            $tracker
                .lock()
                .await
                .add_request_raw($input, "".to_string());
        }
        $res
    }};
    ($tracker:expr, $input:expr, $res:expr, $output:expr) => {{
        if $res.is_ok() {
            $tracker.lock().await.add_request_raw($input, $output);
        }
        $res
    }};
}

pub struct Deployment<M: ?Sized + Model> {
    model: Box<M>,
    usage_tracker: Option<Mutex<UsageTracker>>,
}

impl<M: ?Sized + Model> Deployment<M> {
    pub fn new(model: Box<M>) -> Deployment<M> {
        Self {
            model,
            usage_tracker: None,
        }
    }

    pub fn identifier(&self) -> String {
        self.model.identifier()
    }

    pub fn with_usage_constrain(mut self, rpm: Option<u64>, tpm: Option<u64>) -> Self {
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
            while let time = tracker.lock().await.need_wait_for(need)
                && time > 0
            {
                sleep(Duration::from_millis(time)).await;
            }
            Ok(self)
        } else {
            Ok(self)
        }
    }

    pub async fn min_cooldown_time(&self, input_text: String) -> u64 {
        if let Some(tracker) = &self.usage_tracker {
            tracker.lock().await.need_wait_for_string(input_text)
        } else {
            0
        }
    }

    pub async fn completion(&self, request: CompletionRequest) -> Result<Completion>
    where
        M: CompletionModel,
    {
        if let Some(tracker) = &self.usage_tracker {
            let input = request.message.clone();
            let res = self.model.completion(request).await;
            with_tracking!(
                tracker,
                input,
                res,
                res.as_ref().map(|r| r.to_string()).unwrap_or_default()
            )
        } else {
            self.model.completion(request).await
        }
    }

    pub async fn embedding(&self, request: EmbeddingRequest) -> Result<Embeddings>
    where
        M: EmbeddingModel,
    {
        if let Some(tracker) = &self.usage_tracker {
            let input = request.texts.iter().cloned().collect();
            let res = self.model.embedding(request).await;
            with_tracking!(tracker, input, res)
        } else {
            self.model.embedding(request).await
        }
    }

    pub async fn rerank(&self, request: RerankerRequest) -> Result<Ranking>
    where
        M: RerankerModel,
    {
        if let Some(tracker) = &self.usage_tracker {
            let input = request.documents.iter().cloned().collect();
            let res = self.model.rerank(request).await;
            with_tracking!(tracker, input, res)
        } else {
            self.model.rerank(request).await
        }
    }
}
