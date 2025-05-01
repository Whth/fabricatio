use directories_next::ProjectDirs;
use dotenvy::dotenv_override;
use figment::providers::{Data, Env, Format, Toml};
use figment::value::{Dict, Map};
use figment::{Error, Figment, Metadata, Profile, Provider};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
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


#[derive(Debug, Clone, Deserialize, Serialize, Validate, Default)]
#[pyclass(get_all, set_all)]
pub struct LlmConfig {
    #[validate(url)]
    pub api_endpoint: Option<String>,

    pub api_key: Option<String>,

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


// The library's required configuration.
#[derive(Debug, Deserialize, Serialize, Default)]
#[pyclass(get_all, set_all)]

struct Config {
    /* the library's required/expected values */



    pub llm: LlmConfig,
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
                                body = body.unwrap().get(h).unwrap().as_dict();
                                if body.is_none() {
                                    return (profile, Dict::new());
                                }
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