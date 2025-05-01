use directories_next::ProjectDirs;
use dotenvy::dotenv_override;
use figment::providers::{Data, Env, Format, Toml};
use figment::value::{Dict, Map};
use figment::{Error, Figment, Metadata, Profile, Provider};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::fmt;
use std::fmt::{Debug, Display, Formatter};
use std::path::{Path, PathBuf};
use validator::Validate;
fn get_roaming_config_dir(app_name: &str) -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        // Windows with AppData\Roaming
        ProjectDirs::from("", "", app_name).map(|dirs| dirs.config_dir().to_path_buf())
    }

    #[cfg(any(target_os = "linux", target_os = "android"))]
    {
        // Linux with XDG_CONFIG_HOME or ~/.config
        ProjectDirs::from("", "", app_name).map(|dirs| dirs.config_dir().to_path_buf())
    }

    #[cfg(target_os = "macos")]
    {
        // macOS with ~/Library/Application Support/
        AppDirs::new(Some(app_name), false).map(|dirs| dirs.config_dir().to_path_buf())
    }
}


/// 安全字符串封装，防止敏感内容意外泄露到日志/调试/序列化输出中
#[pyclass]
#[derive(Clone, Deserialize, Serialize)]
pub struct SecretStr {
    source: String,
}

#[pymethods]
impl SecretStr {
    #[new]
    pub fn new(source: &str) -> Self {
        Self {
            source: source.to_string(),
        }
    }
    fn expose(&self) -> &str {
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

    #[validate(range(min = 0.0, max = 2.0, message = "temperature must be between 0.0 and 2.0"))]
    pub temperature: Option<f32>,

    pub stop_sign: Option<Vec<String>>,

    #[validate(range(min = 0.0, max = 1.0, message = "top_p must be between 0.0 and 1.0"))]
    pub top_p: Option<f32>,

    #[validate(range(min = 1, message = "generation_count must be at least 1"))]
    pub generation_count: Option<u32>,

    pub stream: Option<bool>,

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

    pub max_sequence_length: u32,

    pub caching: bool,

    #[validate(url)]
    pub api_endpoint: Option<String>,

    pub api_key: Option<SecretStr>,
}

/// Configuration structure containing all system components
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[pyclass(get_all, set_all)]
pub struct Config {
    /// LLM configuration

    /// Embedding configuration
    pub embedding: EmbeddingConfig,

    pub llm: LLMConfig,
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
            .join(PyprojectToml::new("pyproject.toml", vec!["tool", "fabricatio"]))
            .join(Toml::file(get_roaming_config_dir("fabricatio")
                .expect("Failed to get roaming config dir")
                .join("fabricatio.toml")))
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
        self.toml.data()
            .map(
                |map| {
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
                },
            )
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
    Ok(())
}