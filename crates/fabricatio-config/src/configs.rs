use fabricatio_constants::{TEMPLATES, TEMPLATES_DIRNAME};
use macro_utils::TemplateDefault;
use pyo3::prelude::*;

use crate::secstr::SecretStr;
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::fmt::Debug;
use std::path::PathBuf;
use thryd::tracker::Quota;
use thryd::{DeploymentIdentifier, ProviderName, ProviderType, RouteGroupName};
use validator::Validate;

/// Configuration for Language Learning Models (LLMs) like OpenAI's GPT.
///
/// This structure contains all parameters needed to configure and interact with LLM services.
/// All fields are optional to allow partial configuration from different sources.
#[derive(Debug, Clone, Deserialize, Serialize, Validate, Default)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct LLMConfig {
    pub send_to: Option<String>,

    #[validate(range(
        min = 0.0,
        max = 2.0,
        message = "temperature must be between 0.0 and 2.0"
    ))]
    pub temperature: Option<f32>,

    #[validate(range(min = 0.0, max = 1.0, message = "top_p must be between 0.0 and 1.0"))]
    pub top_p: Option<f32>,

    pub stream: bool,

    #[validate(range(min = 1, message = "max_tokens must be at least 1 if set"))]
    pub max_completion_tokens: Option<u32>,

    #[validate(range(min = -2.0, max = 2.0, message = "presence_penalty must be between -2.0 and 2.0"
    ))]
    pub presence_penalty: Option<f32>,

    #[validate(range(min = -2.0, max = 2.0, message = "frequency_penalty must be between -2.0 and 2.0"
    ))]
    pub frequency_penalty: Option<f32>,
}

/// Embedding configuration structure
#[derive(Debug, Clone, Default, Validate, Deserialize, Serialize)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct EmbeddingConfig {
    pub send_to: Option<String>,
}
#[derive(Debug, Clone, Validate, Deserialize, Serialize)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct DebugConfig {
    pub log_level: String,

    pub log_dir: Option<PathBuf>,
    pub rotation: Option<String>,
}
impl Default for DebugConfig {
    fn default() -> Self {
        DebugConfig {
            log_level: "INFO".to_string(),
            log_dir: None,
            rotation: None,
        }
    }
}

#[derive(Debug, Clone, Validate, Deserialize, Serialize)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct TemplateManagerConfig {
    /// The directory containing the templates.
    pub template_stores: Vec<PathBuf>,

    /// Whether to enable active loading of templates.
    pub active_loading: bool,

    /// The suffix of the templates.
    pub template_suffix: String,
}

impl Default for TemplateManagerConfig {
    fn default() -> Self {
        TemplateManagerConfig {
            template_stores: vec![PathBuf::from(TEMPLATES_DIRNAME), TEMPLATES.clone()],
            active_loading: false,
            template_suffix: "hbs".to_string(),
        }
    }
}

/// Template configuration structure
#[derive(Debug, Clone, Deserialize, Serialize, TemplateDefault)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct TemplateConfig {
    pub mapping_template: String,

    // Task Management Templates
    /// The name of the task briefing template which will be used to brief a task.
    pub task_briefing_template: String,

    /// The name of the dependencies template which will be used to manage dependencies.
    pub dependencies_template: String,

    // Decision Making Templates
    /// The name of the make choice template which will be used to make a choice.
    pub make_choice_template: String,

    /// The name of the make judgment template which will be used to make a judgment.
    pub make_judgment_template: String,

    // String Processing Templates
    ///  The name of the code string template which will be used to generate a code string.
    pub code_string_template: String,

    /// The name of the code snippet template which will be used to generate a code snippet.
    pub code_snippet_template: String,

    /// The name of the generic string template which will be used to review a string.
    pub generic_string_template: String,

    /// The name of the co-validation template which will be used to co-validate a string.
    pub co_validation_template: String,

    /// The name of the liststr template which will be used to display a list of strings.
    pub liststr_template: String,

    /// The name of the pathstr template which will be used to acquire a path of strings.
    pub pathstr_template: String,

    // Object and Data Templates
    /// The name of the create json object template which will be used to create a json object.
    pub create_json_obj_template: String,
}

/// Configuration for a specific provider.
///
/// Contains the necessary details to connect to and authenticate with a service provider.
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct ProviderConfig {
    /// The type of the provider (e.g., OpenAI, Anthropic).
    pub provider_type: ProviderType,

    /// Optional name identifier for the provider instance.
    pub name: Option<ProviderName>,

    /// Optional authentication key for the provider API.
    pub api_key: Option<SecretStr>,

    /// Optional URL endpoint for the provider's API. Must be a valid URL if provided.
    #[validate(url)]
    pub api_endpoint: Option<String>,
}

/// Configuration for a specific deployment.
///
/// Defines the identity, grouping, and rate limits for a deployed service instance.
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct DeploymentConfig {
    /// Unique identifier for the deployment.
    pub identifier: DeploymentIdentifier,

    /// Name of the route group this deployment belongs to.
    pub group: RouteGroupName,

    /// Optional quota limit for tokens per minute (TPM).
    pub tpm: Option<Quota>,

    /// Optional quota limit for requests per minute (RPM).
    pub rpm: Option<Quota>,
}

/// Routing configuration structure for controlling request dispatching behavior.
///
/// Manages the list of available providers and their corresponding deployments
/// to handle load balancing and request routing.
#[derive(Debug, Clone, Default, Deserialize, Serialize, Validate)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct RoutingConfig {
    /// List of configured providers available for routing.
    pub providers: Vec<ProviderConfig>,

    /// List of configured embedding model deployments associated with the providers.
    pub embedding_model_deployments: Vec<DeploymentConfig>,

    /// List of configured completion model deployments associated with the providers.
    pub completion_model_deployments: Vec<DeploymentConfig>,
}

/// General configuration structure for application-wide settings
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct GeneralConfig {
    /// Whether to automatically repair malformed JSON
    pub use_json_repair: bool,
}

impl Default for GeneralConfig {
    fn default() -> Self {
        GeneralConfig {
            use_json_repair: true,
        }
    }
}

/// Pymitter configuration structure
///
/// Contains settings for controlling event emission and listener behavior
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[gen_stub_pyclass]
#[pyclass(from_py_object, get_all, set_all)]
pub struct EmitterConfig {
    /// The delimiter used to separate the event name into segments
    pub delimiter: String,
}

impl Default for EmitterConfig {
    fn default() -> Self {
        EmitterConfig {
            delimiter: "::".to_string(),
        }
    }
}

/// Configuration structure containing all system components
#[derive(Default, Clone, Serialize, Deserialize)]
#[gen_stub_pyclass]
#[pyclass(from_py_object)]
pub struct Config {
    /// Embedding configuration
    ///
    /// Configuration parameters for embedding models, including:
    /// - `model`: Optional model name/identifier
    /// - `dimensions`: Vector dimensions for embeddings
    /// - `timeout`: Request timeout in seconds (min 1)
    /// - `max_sequence_length`: Maximum input sequence length
    /// - `caching`: Enable/disable result caching
    /// - `api_endpoint`: API service URL endpoint
    /// - `api_key`: Authentication key (secure storage)
    #[pyo3(get)]
    pub embedding: EmbeddingConfig,

    /// LLM configuration
    ///
    /// Language Learning Model settings with validation rules:
    /// - `api_endpoint`: Valid URL for API service
    /// - `api_key`: Secure authentication token
    /// - `timeout`: Minimum 1 second
    /// - `max_retries`: Minimum 1 retry attempt
    /// - `model`: Model identifier string
    /// - `temperature`: Range 0.0-2.0 for response randomness
    /// - `stop_sign`: Token generation stop sequence(s)
    /// - `top_p`: Nucleus sampling threshold (0.0-1.0)
    /// - `generation_count`: Minimum 1 completion per prompt
    /// - `stream`: Streaming response flag
    /// - `max_tokens`: Minimum 1 generated tokens
    /// - `rpm`: Requests per minute limit (≥1)
    /// - `tpm`: Tokens per minute limit (≥1)
    /// - `presence_penalty`: Repetition penalty (-2.0-2.0)
    /// - `frequency_penalty`: Frequency-based penalty (-2.0-2.0)
    #[pyo3(get)]
    pub llm: LLMConfig,

    /// Debugging configuration
    ///
    /// Debug settings containing:
    /// - `log_level`: Logging verbosity level (default: "INFO")
    #[pyo3(get)]
    pub debug: DebugConfig,

    /// Template configuration
    ///
    /// Template paths/names for various operations:
    /// - `task_briefing_template`: Task description template
    /// - `dependencies_template`: Dependency management template
    /// - `make_choice_template`: Decision-making template
    /// - `make_judgment_template`: Judgment evaluation template
    /// - `generic_string_template`: General string review template
    /// - `co_validation_template`: String co-validation template
    /// - `liststr_template`: String list display template
    /// - `pathstr_template`: Path string acquisition template
    /// - `create_json_obj_template`: JSON object creation template
    /// - ...
    #[pyo3(get)]
    pub templates: TemplateConfig,

    /// Template manager configuration
    ///
    /// Template loading and management settings:
    /// - `template_dir`: Directories to search for templates
    /// - `active_loading`: Flag to enable template pre-loading
    /// - `template_suffix`: File extension for templates
    #[pyo3(get)]
    pub template_manager: TemplateManagerConfig,

    /// Routing configuration
    ///
    /// Request routing and load balancing settings:
    /// - `max_parallel_requests`: Max concurrent requests
    /// - `allowed_fails`: Failures before circuit breaking
    /// - `retry_after`: Seconds to wait between retries
    /// - `cooldown_time`: Failure cooldown period
    #[pyo3(get)]
    pub routing: RoutingConfig,

    /// General application settings
    ///
    /// Global behavior configuration:
    /// - `confirm_on_ops`: Require operation confirmation
    /// - `use_json_repair`: Auto-repair malformed JSON
    #[pyo3(get)]
    pub general: GeneralConfig,

    /// EventEmitter system configuration
    ///
    /// Event emission control settings:
    /// - `delimiter`: Event name segment separator
    #[pyo3(get)]
    pub emitter: EmitterConfig,

    /// Extension configuration store
    ///
    /// Additional configuration values as key-value pairs.
    /// Used for storing arbitrary extra configuration data.
    pub ext: HashMap<String, Value>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Config {
    /// Load configuration data for a given section name and instantiate a Python class
    ///
    /// This method performs configuration loading with the following behavior:
    /// - Looks up configuration data by section name from extension configuration store
    /// - Converts the data to Python objects using serde serialization
    /// - Instantiates the provided Python class with the configuration data
    ///
    /// # Arguments
    /// * `name` - Name of the configuration section to load
    /// * `cls` - Python class to instantiate, must accept keyword arguments
    ///
    /// # Returns
    /// `PyResult<Bound<'a, PyAny>>` containing either:
    /// - Successfully initialized class instance with loaded config data
    /// - Default-initialized class instance if section not found
    ///
    /// # Errors
    /// Returns PyRuntimeError if:
    /// - Data deserialization to Python types fails
    /// - Class initialization fails with invalid arguments
    fn load<'a>(
        &self,
        python: Python<'a>,
        name: &str,
        cls: Bound<'a, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        if let Some(data) = self.ext.get(name) {
            let any = pythonize(python, data)?;
            cls.call((), Some(&any.cast_into_exact()?))
        } else {
            cls.call((), None)
        }
    }
}
