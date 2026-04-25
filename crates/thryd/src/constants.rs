use std::fmt::{Display, Formatter};

/// Milliseconds in one minute (60,000).
///
/// Used for time conversions and rate limit window calculations.
pub const MINUTE_MS: u64 = 60_000;

/// Maximum size for request/response buffers in bytes.
///
/// Buffers exceeding this size will be rejected to prevent memory issues.
pub const MAX_BUFFER_SIZE: usize = 100_000;

/// Minimum required buffer size in bytes.
///
/// Any buffer smaller than this will cause validation errors.
pub const MIN_BUFFER_SIZE: usize = 50;

/// Separator character used for parsing model IDs and paths.
///
/// Used to split composite identifiers like `"provider/model"` into components.
/// Example: `"openai/gpt-4"` splits on this separator.
pub const SEPARATE: char = '/';

/// Default maximum number of entries in the connection pool cache.
///
/// When the cache exceeds this capacity, the least recently used
/// entries are evicted to make room for new ones.
pub const DEFAULT_MAX_CAPACITY: u64 = 100;

/// Default time-to-live for cache entries, in seconds (3600 = 1 hour).
///
/// Cache entries that haven't been accessed for this duration are
/// automatically evicted on next cache inspection.
pub const DEFAULT_TTL_SECS: u64 = 3600;

/// Duration of each individual time bucket in the sliding window, in seconds.
///
/// Each bucket tracks usage for a fixed 1-second interval. Smaller values
/// provide more granular rate limiting at the cost of higher memory usage.
pub const BUCKET_SIZE_S: usize = 1;

/// Number of buckets in the sliding window rate limiting algorithm.
///
/// With `BUCKET_SIZE_S = 1`, this creates a 60-second sliding window.
/// The window size is `BUCKET_SIZE_S * BUCKET_COUNT` seconds total.
pub const BUCKET_COUNT: usize = 60;

/// Total duration of the sliding window, in seconds.
///
/// This is the product of `BUCKET_SIZE_S` and `BUCKET_COUNT`, representing
/// how far back in time the rate limiter tracks usage. Default: 60 seconds.
///
/// # Rate Limiting Design
/// The sliding window algorithm divides time into `BUCKET_COUNT` discrete slots,
/// each `BUCKET_SIZE_S` seconds apart. When calculating usage:
/// - Each request/token adds to the bucket corresponding to its timestamp
/// - Buckets older than `BUCKETS_WINDOW_S` are considered expired
/// - Total usage = sum of all valid (non-expired) buckets
///
/// This approach is more accurate than fixed-window rate limiting because it
/// smooths out bursts near window boundaries. For example, with a 60 RPM limit:
/// - Fixed window: 30 requests at 0:59, 30 at 1:01 = 60 total but could burst 60/s
/// - Sliding window: Limits burst to 60/min average, distributed naturally
pub const BUCKETS_WINDOW_S: usize = BUCKET_SIZE_S * BUCKET_COUNT;

/// OpenAI API endpoint paths for various operations.
///
/// Each variant corresponds to a specific API endpoint. The `Display`
/// implementation returns the full path including the leading slash.
///
/// # Variants
/// - `ChatCompletions`: Chat completion endpoint (`/chat/completions`)
/// - `Completions`: Legacy text completion endpoint (`/completions`)
/// - `Embeddings`: Text embedding generation (`/embeddings`)
/// - `Model`: Retrieve a specific model (`/models/{model_id}`)
/// - `Models`: List all available models (`/models`)
/// - `FineTuningJobs`: Manage fine-tuning jobs (`/fine_tuning/jobs`)
/// - `FineTuningJob`: Operations on specific job (`/fine_tuning/jobs/{job_id}`)
/// - `Files`: File management endpoint (`/files`)
/// - `File`: Specific file operations (`/files/{file_id}`)
///
/// # Example
/// ```rust
/// use thryd::constants::OpenAiPath;
///
/// let path = OpenAiPath::ChatCompletions;
/// assert_eq!(path.to_string(), "/chat/completions");
///
/// let model_path = OpenAiPath::Model { model_id: "gpt-4".to_string() };
/// assert_eq!(model_path.to_string(), "/models/gpt-4");
/// ```
#[derive(Debug, Clone)]
pub enum OpenAiPath {
    /// Creates chat completions for conversational AI.
    ///
    /// API Path: `/chat/completions`
    /// Use Case: Primary endpoint for ChatGPT-style completions with message history
    ChatCompletions,

    /// Creates legacy text completions (before chat API).
    ///
    /// API Path: `/completions`
    /// Use Case: Older models that use the original completion format
    Completions,

    /// Generates text embeddings for similarity search.
    ///
    /// API Path: `/embeddings`
    /// Use Case: Converting text to vector representations for RAG, similarity
    Embeddings,

    /// Retrieves information about a specific deployed model.
    ///
    /// API Path: `/models/{model_id}`
    /// Use Case: Getting model metadata like capabilities, context window, pricing
    Model {
        /// The unique identifier of the model (e.g., `"gpt-4"`, `"text-embedding-3-small"`)
        model_id: String,
    },

    /// Lists all models available to the organization.
    ///
    /// API Path: `/models`
    /// Use Case: Discovery and enumeration of available models
    Models,

    /// Creates and manages fine-tuning training jobs.
    ///
    /// API Path: `/fine_tuning/jobs`
    /// Use Case: Training custom models on proprietary data
    FineTuningJobs,

    /// Operations on a specific fine-tuning job.
    ///
    /// API Path: `/fine_tuning/jobs/{job_id}`
    /// Use Case: Check status, cancel, or retrieve results of a fine-tuning job
    FineTuningJob {
        /// The unique identifier of the fine-tuning job
        job_id: String,
    },

    /// Lists files in the organization's storage.
    ///
    /// API Path: `/files`
    /// Use Case: Uploading training data, retrieving processed files
    Files,

    /// Upload or retrieve a specific file.
    ///
    /// API Path: `/files/{file_id}`
    /// Use Case: Downloading processed training files, checking upload status
    File {
        /// The unique identifier of the file
        file_id: String,
    },
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
