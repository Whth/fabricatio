//! A module for capturing patterns in text using regular expressions.

use crate::formatter::{generic_block_footer, generic_block_header};
use cfg_if::cfg_if;
use error_mapping::AsPyErr;
use llm_json::repair_json;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyType};
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use regex::{Captures, Regex};
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::path::PathBuf;

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

    fn get_first(captures: Captures) -> String {
        if let Some(mat) = captures.get(1) {
            mat.as_str().to_string()
        } else {
            captures.get(0).unwrap().as_str().to_string()
        }
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl TextCapturer {
    fn cap(&self, text: &str) -> Option<String> {
        self.reg.captures(text).map(Self::get_first)
    }

    fn cap_all(&self, text: &str) -> Vec<String> {
        self.reg.captures_iter(text).map(Self::get_first).collect()
    }
    #[staticmethod]
    pub fn with_pattern(pattern: &str) -> PyResult<Self> {
        Self::new(pattern)
    }

    #[staticmethod]
    #[pyo3(signature=(l_sep=var_names::SNIPPET_LEFT_SEP,r_sep=var_names::SNIPPET_RIGHT_SEP))]
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
    #[pyo3(signature=(language=".*?"))]
    pub fn capture_code_block(language: &str) -> PyResult<Self> {
        Self::capture_content(&format!("```{}", language), Some("```"))
    }

    /// Capture a generic block of the given language.
    ///
    /// Args:
    ///     language (&str): The language or identifier of the generic block.
    ///
    /// Returns:
    ///     PyResult<Self>: An instance of TextCapturer configured to capture generic blocks.
    #[staticmethod]
    #[pyo3(signature=(language=var_names::GENERIC_BLOCK_TYPE))]
    pub fn capture_generic_block(language: &str) -> PyResult<Self> {
        Self::capture_content(
            &generic_block_header(language),
            Some(&generic_block_footer(language)),
        )
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
        Self::new(format!("{}\n(.*?)\n{}", left_delimiter, right))
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

    #[pyo3(signature=(text, elements_type=None, length=None, fix=true))]
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

    #[pyo3(signature=(text, key_type=None, value_type=None, length=None, fix=true))]
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

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct CodeBlockParser {
    capturer: TextCapturer,
    #[pyo3(get)]
    language: String,
}

impl CodeBlockParser {
    fn new(language: &str) -> PyResult<Self> {
        Ok(Self {
            capturer: TextCapturer::capture_code_block(language)?,
            language: language.to_string(),
        })
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl CodeBlockParser {
    /// Create a new CodeBlockParser instance.
    ///
    /// Args:
    ///     language (Option<&str>): The programming language of the code block.
    ///         Capture all kinds of code block if it set to None.
    ///
    /// Returns:
    ///     PyResult<Self>: A new CodeBlockParser instance.
    #[staticmethod]
    pub fn with_language(language: &str) -> PyResult<Self> {
        Self::new(language)
    }

    /// Capture the first code block match in the text.
    ///
    /// Returns the captured code block content or None if no match is found.
    pub fn capture(&self, text: &str) -> Option<String> {
        self.capturer.cap(text)
    }

    /// Capture all code block matches in the text.
    ///
    /// Returns a vector of captured code block contents.
    pub fn capture_all(&self, text: &str) -> Vec<String> {
        self.capturer.cap_all(text)
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct CodeSnippetParser {
    capturer: TextCapturer,
    #[pyo3(get)]
    left_sep: String,
    #[pyo3(get)]
    right_sep: String,
}

impl CodeSnippetParser {
    fn new(l_sep: &str, r_sep: &str) -> PyResult<Self> {
        Ok(Self {
            capturer: TextCapturer::capture_snippet(l_sep, r_sep)?,
            left_sep: l_sep.to_string(),
            right_sep: r_sep.to_string(),
        })
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl CodeSnippetParser {
    /// Create a new CodeSnippetParser instance.
    ///
    /// Args:
    ///     left_sep (&str): The left separator marking the start of the snippet.
    ///     right_sep (&str): The right separator marking the end of the snippet.
    ///
    /// Returns:
    ///     PyResult<Self>: A new CodeSnippetParser instance.
    #[staticmethod]
    #[pyo3(signature=(left_sep=var_names::SNIPPET_LEFT_SEP, right_sep=var_names::SNIPPET_RIGHT_SEP)
    )]
    pub fn with_separators(left_sep: &str, right_sep: &str) -> PyResult<Self> {
        Self::new(left_sep, right_sep)
    }

    /// Parse text into path-content pairs.
    ///
    /// Captures all snippet matches from the text and groups them into pairs,
    /// where each pair consists of a path and its corresponding content.
    ///
    /// Returns:
    ///     Vec<(PathBuf, String)>: A vector of tuples containing the path
    ///     and content for each matched snippet.
    pub fn parse(&self, text: &str) -> Vec<(PathBuf, String)> {
        self.capturer
            .cap_all(text)
            .chunks(2)
            .filter_map(|e| {
                if let [path, content] = e {
                    Some((PathBuf::new().join(path), content.to_string()))
                } else {
                    None
                }
            })
            .collect()
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct GenericBlockParser {
    capturer: TextCapturer,
    #[pyo3(get)]
    block_type: String,
}

impl GenericBlockParser {
    fn new(block_type: &str) -> PyResult<Self> {
        Ok(Self {
            capturer: TextCapturer::capture_generic_block(block_type)?,
            block_type: block_type.to_string(),
        })
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl GenericBlockParser {
    /// Create a new GenericBlockParser instance.
    ///
    /// Args:
    ///     block_type (&str): The type identifier of the generic block.
    ///
    /// Returns:
    ///     PyResult<Self>: A new GenericBlockParser instance.
    #[staticmethod]
    #[pyo3(signature=(block_type=var_names::GENERIC_BLOCK_TYPE))]
    pub fn with_block_type(block_type: &str) -> PyResult<Self> {
        Self::new(block_type)
    }

    /// Capture the first generic block match in the text.
    ///
    /// Returns the captured block content or None if no match is found.
    pub fn capture(&self, text: &str) -> Option<String> {
        self.capturer.cap(text)
    }

    /// Capture all generic block matches in the text.
    ///
    /// Returns a vector of captured block contents.
    pub fn capture_all(&self, text: &str) -> Vec<String> {
        self.capturer.cap_all(text)
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct ContentBlockParser {
    capturer: TextCapturer,
    #[pyo3(get)]
    left_delimiter: String,
    #[pyo3(get)]
    right_delimiter: String,
}

impl ContentBlockParser {
    fn new(left_delimiter: &str, right_delimiter: Option<&str>) -> PyResult<Self> {
        let right = right_delimiter.unwrap_or(left_delimiter);
        Ok(Self {
            capturer: TextCapturer::capture_content(left_delimiter, right_delimiter)?,
            left_delimiter: left_delimiter.to_string(),
            right_delimiter: right.to_string(),
        })
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl ContentBlockParser {
    /// Create a new ContentBlockParser instance.
    ///
    /// Args:
    ///     left_delimiter (&str): The left delimiter marking the start of the content.
    ///     right_delimiter (Option<&str>): The right delimiter marking the end of the content.
    ///         Defaults to left_delimiter if not provided.
    ///
    /// Returns:
    ///     PyResult<Self>: A new ContentBlockParser instance.
    #[staticmethod]
    #[pyo3(signature=(left_delimiter, right_delimiter=None))]
    pub fn with_delimiters(left_delimiter: &str, right_delimiter: Option<&str>) -> PyResult<Self> {
        Self::new(left_delimiter, right_delimiter)
    }

    /// Capture the first content block match in the text.
    ///
    /// Returns the captured content or None if no match is found.
    pub fn capture(&self, text: &str) -> Option<String> {
        self.capturer.cap(text)
    }

    /// Capture all content block matches in the text.
    ///
    /// Returns a vector of captured contents.
    pub fn capture_all(&self, text: &str) -> Vec<String> {
        self.capturer.cap_all(text)
    }
}

mod var_names {
    pub const JSON_PARSER: &str = "json_parser";
    pub const PYTHON_PARSER: &str = "python_parser";
    pub const GENERIC_PARSER: &str = "generic_parser";
    pub const SNIPPET_PARSER: &str = "snippet_parser";
    // Default arguments for parsers
    pub const JSON_LANG: &str = "json";
    pub const PYTHON_LANG: &str = "python";
    pub const GENERIC_BLOCK_TYPE: &str = "String";
    pub const SNIPPET_LEFT_SEP: &str = ">>>>>";
    pub const SNIPPET_RIGHT_SEP: &str = "<<<<<";
}

cfg_if!(
    if #[cfg(feature = "stubgen")]    {
        use pyo3_stub_gen::module_variable;
        module_variable!("fabricatio_core.rust", var_names::JSON_PARSER, JsonParser);
        module_variable!("fabricatio_core.rust", var_names::PYTHON_PARSER, CodeBlockParser);
        module_variable!("fabricatio_core.rust", var_names::GENERIC_PARSER, GenericBlockParser);
        module_variable!("fabricatio_core.rust", var_names::SNIPPET_PARSER, CodeSnippetParser);

    }
);

/// Register the Capture class with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TextCapturer>()?;
    m.add_class::<JsonParser>()?;
    m.add_class::<CodeBlockParser>()?;
    m.add_class::<CodeSnippetParser>()?;
    m.add_class::<GenericBlockParser>()?;
    m.add_class::<ContentBlockParser>()?;
    m.add(
        var_names::JSON_PARSER,
        JsonParser::with_capturer(TextCapturer::capture_code_block(var_names::JSON_LANG)?),
    )?;
    m.add(
        var_names::PYTHON_PARSER,
        CodeBlockParser::with_language(var_names::PYTHON_LANG)?,
    )?;
    m.add(
        var_names::GENERIC_PARSER,
        GenericBlockParser::with_block_type(var_names::GENERIC_BLOCK_TYPE)?,
    )?;
    m.add(
        var_names::SNIPPET_PARSER,
        CodeSnippetParser::with_separators(
            var_names::SNIPPET_LEFT_SEP,
            var_names::SNIPPET_RIGHT_SEP,
        )?,
    )?;

    Ok(())
}
