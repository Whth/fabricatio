use pyo3::{pyclass, pymethods};
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use serde::de::Visitor;
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::fmt;
use std::fmt::{Debug, Display, Formatter};

#[derive(Clone)]
#[gen_stub_pyclass]
#[pyclass]
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

#[gen_stub_pymethods]
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
