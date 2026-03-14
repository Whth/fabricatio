use std::fmt::{Display, Formatter};

pub const MINUTE_MS: u64 = 60_000;


pub const MAX_BUFFER_SIZE: usize = 100_000;
pub const MIN_BUFFER_SIZE: usize = 50;


pub const SEPARATE: char = '/';

/// Default cache configuration
pub const DEFAULT_MAX_CAPACITY: u64 = 100;
pub const DEFAULT_TTL_SECS: u64 = 3600;


pub const BUCKET_SIZE_S: usize = 1;
pub const BUCKET_COUNT: usize = 60;


pub const BUCKETS_WINDOW_S: usize = BUCKET_SIZE_S * BUCKET_COUNT;

#[derive(Debug, Clone)]
pub enum OpenAiPath {
    /// Path for creating chat completions: `/chat/completions`
    ChatCompletions,
    /// Path for creating text completions: `/completions`
    Completions,
    /// Path for embedding generation: `/embeddings`
    Embeddings,
    /// Path for retrieving a model by ID: `/models/{model_id}`
    Model { model_id: String },
    /// Path for listing all models: `/models`
    Models,
    /// Path for fine-tuning jobs: `/fine_tuning/jobs`
    FineTuningJobs,
    /// Path for a specific fine-tuning job: `/fine_tuning/jobs/{job_id}`
    FineTuningJob { job_id: String },
    /// Path for listing files: `/files`
    Files,
    /// Path for uploading or retrieving a file: `/files/{file_id}`
    File { file_id: String },
}

impl Display for OpenAiPath {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::ChatCompletions => write!(f, "/chat/completions"),
            Self::Completions => write!(f, "/completions"),
            Self::Embeddings => write!(f, "/embeddings"),
            Self::Model { model_id } => write!(f, "/models/{}", model_id),
            Self::Models => write!(f, "/models"),
            Self::FineTuningJobs => write!(f, "/fine_tuning/jobs"),
            Self::FineTuningJob { job_id } => write!(f, "/fine_tuning/jobs/{}", job_id),
            Self::Files => write!(f, "/files"),
            Self::File { file_id } => write!(f, "/files/{}", file_id),
        }
    }
}