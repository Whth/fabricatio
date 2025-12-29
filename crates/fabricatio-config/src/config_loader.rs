use crate::configs::Config;
use dotenvy::dotenv_override;
use fabricatio_constants::{CONFIG_FILE, GLOBAL_CONFIG_FILE, NAME};
use figment::providers::{Data, Env, Format, Toml};
use figment::value::{Dict, Map};
use figment::{Error, Figment, Metadata, Profile, Provider};
use pyo3::exceptions::PyRuntimeError;
use pyo3::{PyErr, PyResult};
use std::ops::Deref;
use std::path::Path;

impl Config {
    pub fn new() -> PyResult<Self> {
        Config::from(Config::figment()).map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))
    }
    fn figment() -> Figment {
        Figment::new()
            .join({
                let _ = dotenv_override();
                Env::prefixed(format!("{}_", NAME.to_uppercase()).as_str()).split("__")
            })
            .join(Toml::file(CONFIG_FILE))
            .join(PyprojectToml::new(
                "./pyproject.toml",
                vec!["tool", NAME],
            ))
            .join(Toml::file(GLOBAL_CONFIG_FILE.deref()))
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
