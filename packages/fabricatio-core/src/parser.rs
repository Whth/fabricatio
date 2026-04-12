//! A module for capturing patterns in text using regular expressions.

use error_mapping::AsPyErr;
use llm_json::repair_json;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyType};
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use regex::{Captures, Regex};
use serde::de::DeserializeOwned;
use serde_json::Value;

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[derive(Clone)]
#[pyclass(from_py_object)]
pub struct TextCapturer {
    reg: Regex,
}

impl TextCapturer {
    fn new(pattern: impl AsRef<str>) -> PyResult<Self> {
        Ok(Self {
            reg: Regex::new(format!("(?si){}", pattern.as_ref()).as_str()).into_pyresult()?,
        })
    }

    fn get_fist(captures: Captures) -> String {
        captures.get(0).unwrap().as_str().to_string()
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl TextCapturer {
    fn cap(&self, text: &str) -> Option<String> {
        self.reg.captures(text).map(Self::get_fist)
    }

    fn cap_all(&self, text: &str) -> Vec<String> {
        self.reg.captures_iter(text).map(Self::get_fist).collect()
    }
    #[staticmethod]
    #[pyo3(signature=(l_sep=">>>>>",r_sep="<<<<<"))]
    pub fn capture_snippet(l_sep: &str, r_sep: &str) -> PyResult<Self> {
        Self::new(format!(r#"^(.+?)\s*\n^{l_sep}\S*\n(.*?)\n^{r_sep}\s*$"#))
    }

    /// Capture a code block of the given language.
    ///
    /// Args:
    ///     language (Option<&str>): The programming language of the code block.
    ///     Capture all kinds of code block if it set to None.
    ///
    /// Returns:
    ///     PyResult<Self>: An instance of TextCapturer configured to capture code blocks.
    #[staticmethod]
    #[pyo3(signature=(language=None))]
    pub fn capture_code_block(language: Option<&str>) -> PyResult<Self> {
        let lang = language.unwrap_or(".*?");
        Self::new(format!("```{}\n(.*?)\n```", lang))
    }

    /// Capture a generic block of the given language.
    ///
    /// Args:
    ///     language (&str): The language or identifier of the generic block.
    ///
    /// Returns:
    ///     PyResult<Self>: An instance of TextCapturer configured to capture generic blocks.
    #[staticmethod]
    #[pyo3(signature=(language="String"))]
    pub fn capture_generic_block(language: &str) -> PyResult<Self> {
        Self::new(format!(
            "--- Start of {} ---\n(.*?)\n--- End of {} ---",
            language, language
        ))
    }

    /// Capture content between delimiters.
    ///
    /// Args:
    ///     left_delimiter (&str): The left delimiter marking the start of the content.
    ///     right_delimiter (Option<&str>): The right delimiter marking the end of the content.
    ///
    /// Returns:
    ///     PyResult<Self>: An instance of TextCapturer configured to capture content between delimiters.
    ///
    /// Note:
    ///     - If `right_delimiter` is not provided, it defaults to `left_delimiter`.
    #[staticmethod]
    #[pyo3(signature=(left_delimiter,right_delimiter=None))]
    pub fn capture_content(left_delimiter: &str, right_delimiter: Option<&str>) -> PyResult<Self> {
        let right = right_delimiter.unwrap_or(left_delimiter);
        Self::new(format!("{}(.*?){}", left_delimiter, right))
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct JsonParser {
    capturer: TextCapturer,
}

impl JsonParser {
    fn fix_json_string(json: impl AsRef<str>) -> PyResult<String> {
        repair_json(json.as_ref(), &Default::default()).into_pyresult()
    }
    fn deserialize<T: DeserializeOwned>(text: impl AsRef<str>, fix: bool) -> PyResult<T> {
        if fix {
            serde_json::from_str::<T>(Self::fix_json_string(text)?.as_str()).into_pyresult()
        } else {
            serde_json::from_str::<T>(text.as_ref()).into_pyresult()
        }
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl JsonParser {
    /// Create a new Capture instance.
    #[staticmethod]
    pub fn with_pattern(pattern: &str) -> PyResult<Self> {
        Ok(Self {
            capturer: TextCapturer::new(pattern)?,
        })
    }

    #[staticmethod]
    pub fn with_capturer(capturer: TextCapturer) -> Self {
        Self { capturer }
    }

    /// Capture the first match of the pattern in the text.
    ///
    /// Returns the captured text or None if no match is found.
    #[pyo3(signature=(text, fix=true))]
    pub fn capture(&self, text: &str, fix: bool) -> PyResult<Option<String>> {
        if fix && let Some(cap_string) = self.capturer.cap(text) {
            Self::fix_json_string(cap_string).map(Some)
        } else {
            Ok(self.capturer.cap(text))
        }
    }

    /// Capture all matches of the pattern in the text.
    ///
    /// Returns a vector of tuples containing captured groups for each match.
    #[pyo3(signature=(text, fix=true))]
    pub fn capture_all(&self, text: &str, fix: bool) -> PyResult<Vec<String>> {
        if fix {
            self.capturer
                .cap_all(text)
                .into_iter()
                .map(Self::fix_json_string)
                .try_collect()
        } else {
            Ok(self.capturer.cap_all(text))
        }
    }
    #[pyo3(signature=(text, fix=true))]
    pub fn convert<'a>(
        &self,
        python: Python<'a>,
        text: &str,
        fix: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        pythonize(python, &Self::deserialize::<Value>(text, fix)?).into_pyresult()
    }

    #[pyo3(signature=(text, fix=true))]
    pub fn convert_all<'a>(
        &self,
        python: Python<'a>,
        text: &str,
        fix: bool,
    ) -> PyResult<Vec<Bound<'a, PyAny>>> {
        self.capture_all(text, fix)?
            .into_iter()
            .map(|json| pythonize(python, &Self::deserialize::<Value>(json, fix)?).into_pyresult())
            .try_collect::<Vec<Bound<PyAny>>>()
    }

    #[pyo3(signature=(text, elements_type, length, fix=true))]
    #[gen_stub(
        override_return_type(type_repr = "typing.List[_T]|None", imports = ("typing",))
    )]
    pub fn validate_list<'a>(
        &self,
        python: Python<'a>,
        text: &str,

        #[gen_stub(override_type(type_repr = "typing.Type[_T]|None"))] elements_type: Option<
            &Bound<PyType>,
        >,
        length: Option<usize>,
        fix: bool,
    ) -> PyResult<Option<Bound<'a, PyList>>> {
        let val = self.convert(python, text, fix)?;
        if let Ok(val_list) = val.cast_into_exact::<PyList>()
            && (length.is_none() || length.is_some_and(|l| val_list.len() == l))
            && (elements_type.is_none()
                || elements_type.is_some_and(|t| {
                    val_list
                        .iter()
                        .all(|item| item.is_instance(t).unwrap_or(false))
                }))
        {
            Ok(Some(val_list))
        } else {
            Ok(None)
        }
    }

    #[pyo3(signature=(text, key_type, value_type, length, fix=true))]
    #[gen_stub(
        override_return_type(type_repr = "typing.Dict[_K, _V]|None", imports = ("typing",))
    )]
    pub fn validate_dict<'a>(
        &self,
        python: Python<'a>,
        text: &str,

        #[gen_stub(override_type(type_repr = "typing.Type[_K]|None"))] key_type: Option<
            &Bound<PyType>,
        >,
        #[gen_stub(override_type(type_repr = "typing.Type[_V]|None"))] value_type: Option<
            &Bound<PyType>,
        >,
        length: Option<usize>,
        fix: bool,
    ) -> PyResult<Option<Bound<'a, PyDict>>> {
        let val = self.convert(python, text, fix)?;
        if let Ok(val_dict) = val.cast_into_exact::<PyDict>()
            && (length.is_none() || length.is_some_and(|l| val_dict.len() == l))
        {
            let key_check = key_type.is_none()
                || key_type.is_some_and(|t| {
                    val_dict
                        .keys()
                        .iter()
                        .all(|item| item.is_instance(t).unwrap_or(false))
                });

            let value_check = value_type.is_none()
                || value_type.is_some_and(|t| {
                    val_dict
                        .values()
                        .iter()
                        .all(|item| item.is_instance(t).unwrap_or(false))
                });

            if key_check && value_check {
                Ok(Some(val_dict))
            } else {
                Ok(None)
            }
        } else {
            Ok(None)
        }
    }
}

/// Register the Capture class with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TextCapturer>()?;
    m.add_class::<JsonParser>()?;
    m.add(
        "json_parser",
        JsonParser::with_capturer(TextCapturer::capture_code_block(Some("json"))?),
    )?;
    m.add(
        "python_parser",
        TextCapturer::capture_code_block(Some("python"))?,
    )?;
    m.add(
        "generic_parser",
        TextCapturer::capture_generic_block("String")?,
    )?;
    m.add(
        "snippet_parser",
        TextCapturer::capture_snippet(">>>>>", "<<<<<")?,
    )?;
    Ok(())
}
