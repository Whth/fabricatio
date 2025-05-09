use directories_next::BaseDirs;
use dotenvy::dotenv_override;
use figment::providers::{Data, Env, Format, Toml};
use figment::value::{Dict, Map};
use figment::{Error, Figment, Metadata, Profile, Provider};
use macro_utils::TemplateDefault;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use serde::de::Visitor;
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::fmt;
use std::fmt::{Debug, Display, Formatter};
use std::path::{Path, PathBuf};
use validator::Validate;

fn get_roaming_dir(app_name: &str) -> Option<PathBuf> {
    BaseDirs::new().map(|dirs| dirs.config_dir().join(app_name))
}

#[pyclass]
#[derive(Clone)]
pub struct SecretStr {
    source: String,
}

struct SecStrVisitor;

impl<'de> Visitor<'de> for SecStrVisitor {
    type Value = SecretStr;

    fn expecting(&self, formatter: &mut Formatter) -> fmt::Result {
        formatter.write_str("A string containing a secret value.")
    }
    fn visit_str<E>(self, v: &str) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(v.into())
    }

    fn visit_string<E>(self, v: String) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(v.into())
    }
}

impl<S: AsRef<str>> From<S> for SecretStr {
    fn from(source: S) -> Self {
        Self {
            source: source.as_ref().to_string(),
        }
    }
}

impl<'de> Deserialize<'de> for SecretStr {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_string(SecStrVisitor)
    }
}

impl Serialize for SecretStr {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str("SecretStr(REDACTED)")
    }
}

#[pymethods]
impl SecretStr {
    #[new]
    pub fn new(source: &str) -> Self {
        source.into()
    }
    fn get_secret_value(&self) -> &str {
        self.source.as_str()
    }

    fn __str__(&self) -> &str {
        "SecretStr(REDACTED)"
    }

    fn __repr__(&self) -> &str {
        "SecretStr(REDACTED)"
    }
}

impl Debug for SecretStr {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.write_str("SecretStr(REDACTED)")
    }
}

impl Display for SecretStr {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.write_str("REDACTED")
    }
}

/// Configuration for Language Learning Models (LLMs) like OpenAI's GPT.
///
/// This structure contains all parameters needed to configure and interact with LLM services.
/// All fields are optional to allow partial configuration from different sources.
///
/// # Fields
///
/// * `api_endpoint` - The URL endpoint for the LLM API service (e.g., "https://api.openai.com").
///   Must be a valid URL if provided.
///
/// * `api_key` - Authentication key for the LLM service. Should be kept secure and not exposed.
///
/// * `timeout` - Maximum time in seconds to wait for a response from the LLM.
///   Must be at least 1 second if specified.
///
/// * `max_retries` - Number of retry attempts for failed requests.
///   Must be at least 1 if specified.
///
/// * `model` - Name of the LLM model to use (e.g., "gpt-3.5-turbo", "gpt-4").
///
/// * `temperature` - Controls randomness in response generation. Higher values (up to 2.0) make output
///   more random, while lower values make it more deterministic. Must be between 0.0 and 2.0.
///
/// * `stop_sign` - Sequence(s) that signal the LLM to stop generating further tokens.
///
/// * `top_p` - Controls diversity via nucleus sampling. Lower values consider only tokens with
///   higher probability. Must be between 0.0 and 1.0.
///
/// * `generation_count` - Number of completions to generate for each prompt.
///   Must be at least 1 if specified.
///
/// * `stream` - When true, responses are streamed as they're generated rather than returned complete.
///
/// * `max_tokens` - Maximum number of tokens to generate in the response.
///   Must be at least 1 if specified.
///
/// * `rpm` - Rate limit in requests per minute. Used for client-side rate limiting.
///   Must be at least 1 if specified.
///
/// * `tpm` - Rate limit in tokens per minute. Used for client-side rate limiting.
///   Must be at least 1 if specified.
///
/// * `presence_penalty` - Penalizes new tokens based on their presence in the text so far.
///   Range from -2.0 to 2.0. Positive values discourage repetition.
///
/// * `frequency_penalty` - Penalizes new tokens based on their frequency in the text so far.
///   Range from -2.0 to 2.0. Positive values discourage repetition.
#[derive(Debug, Clone, Deserialize, Serialize, Validate, Default)]
#[pyclass(get_all, set_all)]
pub struct LLMConfig {
    #[validate(url)]
    pub api_endpoint: Option<String>,

    pub api_key: Option<SecretStr>,

    #[validate(range(min = 1, message = "timeout must be at least 1 second"))]
    pub timeout: Option<u64>,

    #[validate(range(min = 1, message = "max_retries must be at least 1"))]
    pub max_retries: Option<u32>,

    pub model: Option<String>,

    #[validate(range(
        min = 0.0,
        max = 2.0,
        message = "temperature must be between 0.0 and 2.0"
    ))]
    pub temperature: Option<f32>,

    pub stop_sign: Option<Vec<String>>,

    #[validate(range(min = 0.0, max = 1.0, message = "top_p must be between 0.0 and 1.0"))]
    pub top_p: Option<f32>,

    #[validate(range(min = 1, message = "generation_count must be at least 1"))]
    pub generation_count: Option<u32>,

    pub stream: bool,

    #[validate(range(min = 1, message = "max_tokens must be at least 1 if set"))]
    pub max_tokens: Option<u32>,

    #[validate(range(min = 1, message = "rpm must be at least 1 if set"))]
    pub rpm: Option<u32>,

    #[validate(range(min = 1, message = "tpm must be at least 1 if set"))]
    pub tpm: Option<u32>,

    #[validate(range(min = -2.0, max = 2.0, message = "presence_penalty must be between -2.0 and 2.0"
    ))]
    pub presence_penalty: Option<f32>,

    #[validate(range(min = -2.0, max = 2.0, message = "frequency_penalty must be between -2.0 and 2.0"
    ))]
    pub frequency_penalty: Option<f32>,
}

/// Embedding configuration structure
#[derive(Debug, Clone, Default, Validate, Deserialize, Serialize)]
#[pyclass(get_all, set_all)]
pub struct EmbeddingConfig {
    pub model: Option<String>,

    pub dimensions: Option<u32>,

    #[validate(range(min = 1, message = "timeout must be at least 1 second"))]
    pub timeout: Option<u32>,

    pub max_sequence_length: Option<u32>,

    pub caching: Option<bool>,

    #[validate(url)]
    pub api_endpoint: Option<String>,

    pub api_key: Option<SecretStr>,
}

/// RAG configuration structure
#[derive(Debug, Clone, Deserialize, Serialize, Validate, Default)]
#[pyclass(get_all, set_all)]
pub struct RagConfig {
    #[validate(url)]
    pub milvus_uri: Option<String>,

    #[validate(range(min = 1.0, message = "milvus_timeout must be at least 1.0 second"))]
    pub milvus_timeout: Option<f64>,

    pub milvus_token: Option<SecretStr>,

    pub milvus_dimensions: Option<u32>,
}

#[derive(Debug, Clone, Default, Validate, Deserialize, Serialize)]
#[pyclass(get_all, set_all)]
pub struct DebugConfig {
    log_level: Option<String>,
}

#[derive(Debug, Clone, Validate, Deserialize, Serialize)]
#[pyclass(get_all, set_all)]
pub struct TemplateManagerConfig {
    /// The directory containing the templates.
    pub template_dir: Vec<PathBuf>,

    /// Whether to enable active loading of templates.
    pub active_loading: Option<bool>,

    /// The suffix of the templates.
    pub template_suffix: Option<String>,
}

impl Default for TemplateManagerConfig {
    fn default() -> Self {
        TemplateManagerConfig {
            template_dir: vec![
                PathBuf::from("templates"),
                get_roaming_dir("fabricatio").unwrap().join("templates"),
            ],
            active_loading: Some(true),
            template_suffix: Some("hbs".to_string()),
        }
    }
}

/// Template configuration structure
#[derive(Debug, Clone, Deserialize, Serialize, TemplateDefault)]
#[pyclass(get_all, set_all)]
pub struct TemplateConfig {
    /// The name of the create json object template which will be used to create a json object.
    pub create_json_obj_template: String,

    /// The name of the draft tool usage code template which will be used to draft tool usage code.
    pub draft_tool_usage_code_template: String,

    /// The name of the make choice template which will be used to make a choice.
    pub make_choice_template: String,

    /// The name of the make judgment template which will be used to make a judgment.
    pub make_judgment_template: String,

    /// The name of the dependencies template which will be used to manage dependencies.
    pub dependencies_template: String,

    /// The name of the task briefing template which will be used to brief a task.
    pub task_briefing_template: String,

    /// The name of the rate fine grind template which will be used to rate fine grind.
    pub rate_fine_grind_template: String,

    /// The name of the draft rating manual template which will be used to draft rating manual.
    pub draft_rating_manual_template: String,

    /// The name of the draft rating criteria template which will be used to draft rating criteria.
    pub draft_rating_criteria_template: String,

    /// The name of the extract reasons from examples template which will be used to extract reasons from examples.
    pub extract_reasons_from_examples_template: String,

    /// The name of the extract criteria from reasons template which will be used to extract criteria from reasons.
    pub extract_criteria_from_reasons_template: String,

    /// The name of the draft rating weights klee template which will be used to draft rating weights with Klee method.
    pub draft_rating_weights_klee_template: String,

    /// The name of the retrieved display template which will be used to display retrieved documents.
    pub retrieved_display_template: String,

    /// The name of the liststr template which will be used to display a list of strings.
    pub liststr_template: String,

    /// The name of the refined query template which will be used to refine a query.
    pub refined_query_template: String,

    /// The name of the pathstr template which will be used to acquire a path of strings.
    pub pathstr_template: String,

    /// The name of the review string template which will be used to review a string.
    pub review_string_template: String,

    /// The name of the generic string template which will be used to review a string.
    pub generic_string_template: String,

    /// The name of the co-validation template which will be used to co-validate a string.
    pub co_validation_template: String,

    /// The name of the as prompt template which will be used to convert a string to a prompt.
    pub as_prompt_template: String,

    /// The name of the check string template which will be used to check a string.
    pub check_string_template: String,

    /// The name of the ruleset requirement breakdown template which will be used to breakdown a ruleset requirement.
    pub ruleset_requirement_breakdown_template: String,

    /// The name of the fix troubled object template which will be used to fix a troubled object.
    pub fix_troubled_obj_template: String,

    /// The name of the fix troubled string template which will be used to fix a troubled string.
    pub fix_troubled_string_template: String,

    /// The name of the rule requirement template which will be used to generate a rule requirement.
    pub rule_requirement_template: String,

    /// The name of the extract template which will be used to extract model from string.
    pub extract_template: String,

    /// The name of the chap summary template which will be used to generate a chapter summary.
    pub chap_summary_template: String,
}
/// Routing configuration structure for controlling request dispatching behavior
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[pyclass(get_all, set_all)]
pub struct RoutingConfig {
    /// The maximum number of parallel requests. None means not checked.
    pub max_parallel_requests: Option<u32>,

    /// The number of allowed fails before the routing is considered failed.
    pub allowed_fails: Option<u32>,

    /// Minimum time to wait before retrying a failed request.
    pub retry_after: u32,

    /// Time to cooldown a deployment after failure in seconds.
    pub cooldown_time: Option<u32>,
}

impl Default for RoutingConfig {
    fn default() -> Self {
        RoutingConfig {
            max_parallel_requests: Some(60),
            allowed_fails: Some(3),
            retry_after: 15,
            cooldown_time: Some(60),
        }
    }
}
/// General configuration structure for application-wide settings
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[pyclass(get_all, set_all)]
pub struct GeneralConfig {
    /// Whether to confirm operations before executing them
    pub confirm_on_ops: bool,

    /// Whether to automatically repair malformed JSON
    pub use_json_repair: bool,
}

impl Default for GeneralConfig {
    fn default() -> Self {
        GeneralConfig {
            confirm_on_ops: true,
            use_json_repair: true,
        }
    }
}

/// Configuration for toolbox functionality
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[pyclass(get_all, set_all)]
pub struct ToolBoxConfig {
    /// The name of the module containing the toolbox.
    pub tool_module_name: String,

    /// The name of the module containing the data.
    pub data_module_name: String,
}

impl Default for ToolBoxConfig {
    fn default() -> Self {
        ToolBoxConfig {
            tool_module_name: "Toolbox".to_string(),
            data_module_name: "Data".to_string(),
        }
    }
}

/// Pymitter configuration structure
///
/// Contains settings for controlling event emission and listener behavior
#[derive(Debug, Clone, Deserialize, Serialize, Validate)]
#[pyclass(get_all, set_all)]
pub struct PymitterConfig {
    /// The delimiter used to separate the event name into segments
    pub delimiter: String,

    /// If set, a newListener event is emitted when a new listener is added
    pub new_listener_event: bool,

    /// The maximum number of listeners per event. -1 means unlimited
    pub max_listeners: i32,
}

impl Default for PymitterConfig {
    fn default() -> Self {
        PymitterConfig {
            delimiter: "::".to_string(),
            new_listener_event: false,
            max_listeners: -1,
        }
    }
}

/// Configuration structure containing all system components
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[pyclass(get_all, set_all)]
pub struct Config {
    /// LLM configuration

    /// Embedding configuration
    pub embedding: EmbeddingConfig,

    pub llm: LLMConfig,

    pub debug: DebugConfig,

    pub rag: RagConfig,

    pub templates: TemplateConfig,

    pub template_manager: TemplateManagerConfig,

    pub routing: RoutingConfig,

    pub general: GeneralConfig,

    pub toolbox: ToolBoxConfig,

    pub pymitter: PymitterConfig,
}

#[pymethods]
impl Config {
    // Provide a default provider, a `Figment`.
    #[new]
    fn new() -> PyResult<Self> {
        Config::from(Config::figment()).map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))
    }
}

impl Config {
    fn figment() -> Figment {
        Figment::new()
            .join({
                dotenv_override().expect("Failed to load .env file");
                Env::prefixed("FABRIK_").split("__")
            })
            .join(Toml::file("fabricatio.toml"))
            .join(PyprojectToml::new(
                "pyproject.toml",
                vec!["tool", "fabricatio"],
            ))
            .join(Toml::file(
                get_roaming_dir("fabricatio")
                    .expect("Failed to get roaming config dir")
                    .join("fabricatio.toml"),
            ))
            .join(Config::default())
    }

    // Allow the configuration to be extracted from any `Provider`.
    fn from<T: Provider>(provider: T) -> Result<Config, String> {
        Figment::from(provider).extract().map_err(|e| e.to_string())
    }
}

/// discover extra config within the pyproject.toml file
struct PyprojectToml {
    toml: Data<Toml>,
    header: Vec<&'static str>,
}

impl PyprojectToml {
    fn new<P: AsRef<Path>>(path: P, header: Vec<&'static str>) -> Self {
        Self {
            toml: Toml::file(path),
            header,
        }
    }
}

impl Provider for PyprojectToml {
    fn metadata(&self) -> Metadata {
        Metadata::named("Pyproject Toml File")
    }

    fn data(&self) -> Result<Map<Profile, Dict>, Error> {
        self.toml.data().map(|map| {
            map.into_iter()
                .map(|(profile, dict)| {
                    let mut body: Option<&Dict> = Some(&dict);

                    for &h in self.header.iter() {
                        if !body.unwrap().contains_key(h) {
                            return (profile, Dict::new());
                        }
                        body = body.unwrap().get(h).unwrap().as_dict();
                    }
                    (profile, body.unwrap().to_owned())
                })
                .collect()
        })
    }
}

// Make `Config` a provider itself for composability.
impl Provider for Config {
    fn metadata(&self) -> Metadata {
        Metadata::named("Fabricatio Default Config")
    }

    fn data(&self) -> Result<Map<Profile, Dict>, Error> {
        figment::providers::Serialized::defaults(Config::default()).data()
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Config>()?;
    m.add_class::<TemplateManagerConfig>()?;

    m.add_class::<LLMConfig>()?;
    m.add_class::<EmbeddingConfig>()?;
    m.add_class::<DebugConfig>()?;
    m.add_class::<RagConfig>()?;
    m.add_class::<TemplateConfig>()?;
    m.add_class::<RoutingConfig>()?;
    m.add_class::<GeneralConfig>()?;
    m.add_class::<ToolBoxConfig>()?;
    m.add_class::<PymitterConfig>()?;
    m.add_class::<SecretStr>()?;

    m.add("CONFIG", Config::new()?)?;

    Ok(())
}
