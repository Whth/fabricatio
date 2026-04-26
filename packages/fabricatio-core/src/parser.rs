//! A module for capturing patterns in text using regular expressions.

use crate::formatter::{generic_block_footer, generic_block_header};
use cfg_if::cfg_if;
use error_mapping::AsPyErr;
use fabricatio_logger::warn;
use llm_json::repair_json;
use once_cell::sync::Lazy;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyType};
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use regex::{Captures, Regex};
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::collections::HashMap;
use std::fs::File;
use std::io::Write;
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
            reg: Regex::new(format!("(?smi){}", pattern.as_ref()).as_str()).into_pyresult()?,
        })
    }

    pub fn get_group_1(captures: Captures) -> String {
        captures.get(1).unwrap().as_str().to_string()
    }

    pub fn get_group_2(captures: Captures) -> (String, String) {
        (
            captures.get(1).unwrap().as_str().to_string(),
            captures.get(2).unwrap().as_str().to_string(),
        )
    }

    pub fn get_group_3(captures: Captures) -> (String, String, String) {
        (
            captures.get(1).unwrap().as_str().to_string(),
            captures.get(2).unwrap().as_str().to_string(),
            captures.get(3).unwrap().as_str().to_string(),
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl TextCapturer {
    /// Captures the first match and extracts group 1.
    ///
    /// Args:
    ///     text: The text to search within.
    ///
    /// Returns:
    ///     The first captured group if a match is found.
    fn cap1(&self, text: &str) -> Option<String> {
        self.reg.captures(text).map(Self::get_group_1)
    }

    /// Captures all matches and extracts group 1 from each.
    ///
    /// Args:
    ///     text: The text to search within.
    ///
    /// Returns:
    ///     A list of first captured groups from all matches.
    fn cap1_all(&self, text: &str) -> Vec<String> {
        self.reg
            .captures_iter(text)
            .map(Self::get_group_1)
            .collect()
    }

    /// Captures the first match and extracts groups 1 and 2.
    ///
    /// Args:
    ///     text: The text to search within.
    ///
    /// Returns:
    ///     A tuple of (group1, group2) if a match is found.
    fn cap2(&self, text: &str) -> Option<(String, String)> {
        self.reg.captures(text).map(Self::get_group_2)
    }

    /// Captures all matches and extracts groups 1 and 2 from each.
    ///
    /// Args:
    ///     text: The text to search within.
    ///
    /// Returns:
    ///     A list of (group1, group2) tuples from all matches.
    fn cap2_all(&self, text: &str) -> Vec<(String, String)> {
        self.reg
            .captures_iter(text)
            .map(Self::get_group_2)
            .collect()
    }

    /// Captures the first match and extracts groups 1, 2, and 3.
    ///
    /// Args:
    ///     text: The text to search within.
    ///
    /// Returns:
    ///     A tuple of (group1, group2, group3) if a match is found.
    fn cap3(&self, text: &str) -> Option<(String, String, String)> {
        self.reg.captures(text).map(Self::get_group_3)
    }

    /// Captures all matches and extracts groups 1, 2, and 3 from each.
    ///
    /// Args:
    ///     text: The text to search within.
    ///
    /// Returns:
    ///     A list of (group1, group2, group3) tuples from all matches.
    fn cap3_all(&self, text: &str) -> Vec<(String, String, String)> {
        self.reg
            .captures_iter(text)
            .map(Self::get_group_3)
            .collect()
    }

    /// Creates a TextCapturer with a custom regex pattern.
    ///
    /// Args:
    ///     pattern: The regex pattern to use.
    ///
    /// Returns:
    ///     A new TextCapturer instance.
    #[staticmethod]
    pub fn with_pattern(pattern: &str) -> PyResult<Self> {
        Self::new(pattern)
    }

    /// Creates a TextCapturer for capturing code snippets with separators.
    ///
    /// Args:
    ///     l_sep: The left separator (default: ">>>>>").
    ///     r_sep: The right separator (default: "<<<<<").
    ///
    /// Returns:
    ///     A new TextCapturer instance configured for snippets.
    #[staticmethod]
    #[pyo3(signature=(l_sep=var_names::SNIPPET_LEFT_SEP,r_sep=var_names::SNIPPET_RIGHT_SEP))]
    pub fn capture_snippet(l_sep: &str, r_sep: &str) -> PyResult<Self> {
        Self::new(format!(r"^(.*?)\n{l_sep}(.*?)\n(.*?)\n{r_sep}$"))
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
#[derive(Clone)]
#[pyclass(from_py_object)]
pub struct JsonParser {
    capturer: TextCapturer,
}

impl JsonParser {
    fn fix_json_string(json: impl AsRef<str>) -> PyResult<String> {
        repair_json(json.as_ref(), &Default::default()).into_pyresult()
    }
    pub fn deserialize<T: DeserializeOwned>(text: impl AsRef<str>, fix: bool) -> PyResult<T> {
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
    /// Creates a JsonParser with a custom regex pattern.
    ///
    /// Args:
    ///     pattern: The regex pattern to use for capturing JSON.
    ///
    /// Returns:
    ///     A new JsonParser instance.
    #[staticmethod]
    pub fn with_pattern(pattern: &str) -> PyResult<Self> {
        Ok(Self {
            capturer: TextCapturer::new(pattern)?,
        })
    }

    /// Creates a JsonParser with an existing TextCapturer.
    ///
    /// Args:
    ///     capturer: The TextCapturer to use.
    ///
    /// Returns:
    ///     A new JsonParser instance.
    #[staticmethod]
    pub fn with_capturer(capturer: TextCapturer) -> Self {
        Self { capturer }
    }
    #[staticmethod]
    pub fn capture_json_codeblock() -> Self {
        JsonParser::with_capturer(TextCapturer::capture_code_block(var_names::JSON_LANG).unwrap())
    }

    /// Captures and optionally repairs the first JSON match in text.
    ///
    /// Args:
    ///     text: The text to search within.
    ///     fix: Whether to attempt JSON repair on the captured content.
    ///
    /// Returns:
    ///     The captured text or None if no match is found.
    #[pyo3(signature=(text, fix=true))]
    pub fn capture(&self, text: &str, fix: bool) -> Option<String> {
        if fix && let Some(cap_string) = self.capturer.cap1(text) {
            Self::fix_json_string(cap_string).ok()
        } else {
            self.capturer.cap1(text)
        }
    }

    /// Captures and optionally repairs all JSON matches in text.
    ///
    /// Args:
    ///     text: The text to search within.
    ///     fix: Whether to attempt JSON repair on each captured content.
    ///
    /// Returns:
    ///     A list of captured JSON strings.
    #[pyo3(signature=(text, fix=true))]
    pub fn capture_all(&self, text: &str, fix: bool) -> Vec<String> {
        if fix {
            self.capturer
                .cap1_all(text)
                .into_iter()
                .filter_map(|e| Self::fix_json_string(e).ok())
                .collect()
        } else {
            self.capturer.cap1_all(text)
        }
    }

    /// Converts captured text to a Python object.
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The parsed Python object or None if conversion fails.
    #[pyo3(signature=(text, fix=true))]
    pub fn convert<'a>(
        &self,
        python: Python<'a>,
        text: &str,
        fix: bool,
    ) -> Option<Bound<'a, PyAny>> {
        let val = Self::deserialize::<Value>(text, fix).ok()?;
        let py_val = pythonize(python, &val);
        if py_val.is_err() {
            warn!("JsonParser: failed to convert text");
        }
        py_val.ok()
    }

    /// Converts all captured JSON strings to Python objects.
    ///
    /// Args:
    ///     text: The text to search within.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     A list of parsed Python objects.
    #[pyo3(signature=(text, fix=true))]
    pub fn convert_all<'a>(
        &self,
        python: Python<'a>,
        text: &str,
        fix: bool,
    ) -> Vec<Bound<'a, PyAny>> {
        self.capture_all(text, fix)
            .into_iter()
            .filter_map(|json| pythonize(python, &Self::deserialize::<Value>(json, fix).ok()?).ok())
            .collect()
    }

    /// Validates that the text parses to a list with optional constraints.
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     elements_type: Optional type to check all elements against.
    ///     length: Optional exact length requirement.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The validated list or None if validation fails.
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
    ) -> Option<Bound<'a, PyList>> {
        let val_list = self.convert(python, text, fix)
            .and_then(|val| {
                val.cast_into_exact::<PyList>()
                    .map_err(|_| {
                        warn!(
                            "validate_list: validation failed for text with length={:?}, elements_type={:?}",
                            length,
                            elements_type.map(|t| t.to_string())
                        );
                    })
                    .ok()
            })?;

        let len = val_list.len();
        if let Some(l) = length
            && l != 0 && len != l {
                warn!("validate_list: length mismatch - expected {:?}, got {}", length, len);
                return None;
            }

        if let Some(t) = elements_type
            && !val_list.iter().all(|item| item.is_instance(t).unwrap_or(false)) {
                warn!("validate_list: element type check failed for type={:?}", t.to_string());
                return None;
            }

        Some(val_list)
    }


    pub fn validate_list_str(&self, text: &str, length: Option<usize>, fix: bool) -> Option<Vec<String>> {
        let val = Self::deserialize::<Vec<String>>(text, fix).ok()?;
        let len = val.len();
        if let Some(l) = length
            && l != 0 && len != l {
                warn!("validate_list_str: length mismatch - expected {:?}, got {}", length, len);
                return None;
            }
        Some(val)
    }

    /// Validates that the text parses to a dictionary with optional constraints.
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     key_type: Optional type to check all keys against.
    ///     value_type: Optional type to check all values against.
    ///     length: Optional exact length requirement.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The validated dictionary or None if validation fails.
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
    ) -> Option<Bound<'a, PyDict>> {
        let val_dict = self.convert(python, text, fix)
            .and_then(|val| {
                val.cast_into_exact::<PyDict>()
                    .map_err(|_| {
                        warn!("validate_dict: validation failed for text with length={:?}", length);
                    })
                    .ok()
            })?;


        let len = val_dict.len();
        if let Some(l) = length
            && l != 0 && len != l {
                warn!("validate_dict: length mismatch - expected {:?}, got {}", length, len);
                return None;
            }

        if let Some(t) = key_type
            && !val_dict.keys().iter().all(|item| item.is_instance(t).unwrap_or(false)) {
                warn!("validate_dict: type check failed with key_type={:?}", t.to_string());
                return None;
            }

        if let Some(t) = value_type
            && !val_dict.values().iter().all(|item| item.is_instance(t).unwrap_or(false)) {
                warn!("validate_dict: type check failed with value_type={:?}", t.to_string());
                return None;
            }

        Some(val_dict)
    }

    pub fn validate_dict_str_str(
        &self,
        text: &str,
        length: Option<usize>,
        fix: bool,
    ) -> Option<HashMap<String, String>> {
        let val = Self::deserialize::<HashMap<String, String>>(text, fix).ok()?;
        let len = val.len();
        if let Some(l) = length
            && l != 0 && len != l {
                warn!("validate_dict_str_str: length mismatch - expected {:?}, got {}", length, len);
                return None;
            }
        Some(val)
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[derive(Clone)]
#[pyclass(from_py_object)]
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

    #[staticmethod]
    pub fn capture_python() -> Self {
        Self::with_language(var_names::PYTHON_LANG).unwrap()
    }

    /// Capture the first code block match in the text.
    ///
    /// Returns the captured code block content or None if no match is found.
    pub fn capture(&self, text: &str) -> Option<String> {
        self.capturer.cap1(text)
    }

    /// Capture all code block matches in the text.
    ///
    /// Returns a vector of captured code block contents.
    pub fn capture_all(&self, text: &str) -> Vec<String> {
        self.capturer.cap1_all(text)
    }
}
/// Represents a code snippet extracted from text.
///
///
/// Contains its source code, programming language, and the target file path for writing.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(get_all)]
pub struct CodeSnippet {
    /// The source code content of the snippet.
    source: String,
    /// The programming language of the snippet.
    language: String,
    /// The file path where the snippet should be written.
    write_to: PathBuf,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl CodeSnippet {
    /// Writes the code snippet to its designated file path.
    ///
    /// Args:
    ///     parent_dirs: Whether to create parent directories if they don't exist.
    ///
    /// Returns:
    ///     PyResult<()> indicating success.
    #[pyo3(signature=(parent_dirs=true))]
    pub fn write(&self, parent_dirs: bool) -> PyResult<()> {
        if parent_dirs
            && let Some(parent) = self.write_to.parent()
            && !parent.exists()
        {
            std::fs::create_dir_all(parent).into_pyresult()?;
        }

        let mut file = File::create(&self.write_to).into_pyresult()?;
        file.write_all(self.source.as_bytes()).into_pyresult()?;
        Ok(())
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[derive(Clone)]
#[pyclass(from_py_object)]
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

    #[staticmethod]
    pub fn default() -> Self {
        Self::with_separators(
            var_names::SNIPPET_LEFT_SEP,
            var_names::SNIPPET_RIGHT_SEP,
        ).unwrap()
    }


    /// Parse text into path-content pairs.
    ///
    /// Captures all snippet matches from the text and groups them into pairs,
    /// where each pair consists of a path and its corresponding content.
    ///
    /// Returns:
    ///     Vec<(PathBuf, String)>: A vector of tuples containing the path
    ///     and content for each matched snippet.
    pub fn parse(&self, text: &str) -> Vec<CodeSnippet> {
        self.capturer
            .cap3_all(text)
            .into_iter()
            .map(|(write_to, language, source)| CodeSnippet {
                write_to: PathBuf::new().join(write_to),
                language,
                source,
            })
            .collect()
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[derive(Clone)]
#[pyclass(from_py_object)]
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

    #[staticmethod]
    pub fn capture_generic_string() -> Self {
        GenericBlockParser::with_block_type(var_names::GENERIC_BLOCK_TYPE).unwrap()
    }


    /// Capture the first generic block match in the text.
    ///
    /// Returns the captured block content or None if no match is found.
    pub fn capture(&self, text: &str) -> Option<String> {
        self.capturer.cap1(text)
    }

    /// Capture all generic block matches in the text.
    ///
    /// Returns a vector of captured block contents.
    pub fn capture_all(&self, text: &str) -> Vec<String> {
        self.capturer.cap1_all(text)
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[derive(Clone)]
#[pyclass(from_py_object)]
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
        self.capturer.cap1(text)
    }

    /// Capture all content block matches in the text.
    ///
    /// Returns a vector of captured contents.
    pub fn capture_all(&self, text: &str) -> Vec<String> {
        self.capturer.cap1_all(text)
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
        module_variable!("fabricatio_core.rust", "GENERIC_BLOCK_TYPE", &str,var_names::GENERIC_BLOCK_TYPE);
        module_variable!("fabricatio_core.rust", "SNIPPET_LEFT_SEP",  &str,var_names::SNIPPET_LEFT_SEP);
        module_variable!("fabricatio_core.rust", "SNIPPET_RIGHT_SEP",  &str,var_names::SNIPPET_RIGHT_SEP);

    }
);






pub static JSON_PARSER: Lazy<JsonParser> = Lazy::new(JsonParser::capture_json_codeblock);

pub static PYTHON_PARSER: Lazy<CodeBlockParser> = Lazy::new(CodeBlockParser::capture_python);


pub static GENERIC_PARSER: Lazy<GenericBlockParser> = Lazy::new(GenericBlockParser::capture_generic_string);


pub static SNIPPET_PARSER: Lazy<CodeSnippetParser> = Lazy::new(CodeSnippetParser::default);
/// Registers the parser classes with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TextCapturer>()?;
    m.add_class::<JsonParser>()?;
    m.add_class::<CodeBlockParser>()?;
    m.add_class::<CodeSnippetParser>()?;
    m.add_class::<CodeSnippet>()?;
    m.add_class::<GenericBlockParser>()?;
    m.add_class::<ContentBlockParser>()?;
    m.add(
        var_names::JSON_PARSER,
        JSON_PARSER.to_owned(),
    )?;
    m.add(
        var_names::PYTHON_PARSER,
        PYTHON_PARSER.to_owned(),
    )?;
    m.add(
        var_names::GENERIC_PARSER,
        GENERIC_PARSER.to_owned(),
    )?;
    m.add(
        var_names::SNIPPET_PARSER,
        SNIPPET_PARSER.to_owned(),
    )?;

    Ok(())
}
