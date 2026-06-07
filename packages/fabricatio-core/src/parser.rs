//! A module for capturing patterns in text using regular expressions.

use crate::formatter::{generic_block_footer, generic_block_header};
use cfg_if::cfg_if;
use error_mapping::AsPyErr;
use fabricatio_logger::warn;
use llm_json::repair_json;
use once_cell::sync::Lazy;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PySet, PyString, PyType};
use pyo3_stub_gen::derive::*;
use pythonize::pythonize;
use regex::{Captures, Regex};
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::hash::Hash;
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
#[cfg_attr(feature = "stubgen", gen_stub_pyclass_enum)]
#[derive(Clone)]
#[pyclass(from_py_object)]
pub enum ValueType {
    String,
    Float,
    Int,
    Bool,
}
#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl ValueType {
    /// Create a ValueType from a Python type.
    #[staticmethod]
    pub fn from_type(py_type: Bound<PyType>) -> PyResult<Self> {
        if py_type.is_subclass_of::<PyFloat>()? {
            Ok(ValueType::Float)
        } else if py_type.is_subclass_of::<PyInt>()? {
            Ok(ValueType::Int)
        } else if py_type.is_subclass_of::<PyBool>()? {
            Ok(ValueType::Bool)
        } else if py_type.is_subclass_of::<PyString>()? {
            Ok(ValueType::String)
        } else {
            Err(pyo3::exceptions::PyTypeError::new_err(format!(
                "Unsupported type: {}",
                py_type.fully_qualified_name()?
            )))
        }
    }
}

/// A validated dictionary result typed by key/value kinds.
///
/// Each variant wraps a `HashMap` with concrete Rust types, eliminating
/// the need for `pythonize` at the validation boundary. Callers that need
/// a Python object invoke [`into_py_any`](ValidatedDict::into_py_any) explicitly.
#[derive(Clone)]
pub enum ValidatedDict {
    StringString(HashMap<String, String>),
    StringFloat(HashMap<String, f64>),
    StringInt(HashMap<String, i64>),
    StringBool(HashMap<String, bool>),
    IntString(HashMap<i64, String>),
    IntFloat(HashMap<i64, f64>),
    IntInt(HashMap<i64, i64>),
    IntBool(HashMap<i64, bool>),
    BoolString(HashMap<bool, String>),
    BoolFloat(HashMap<bool, f64>),
    BoolInt(HashMap<bool, i64>),
    BoolBool(HashMap<bool, bool>),
}

impl ValidatedDict {
    /// Convert into a Python object via `pythonize`.
    pub fn into_py_any(self, py: Python) -> Bound<PyAny> {
        match self {
            ValidatedDict::StringString(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::StringFloat(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::StringInt(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::StringBool(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::IntString(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::IntFloat(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::IntInt(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::IntBool(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::BoolString(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::BoolFloat(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::BoolInt(v) => pythonize(py, &v).unwrap(),
            ValidatedDict::BoolBool(v) => pythonize(py, &v).unwrap(),
        }
    }
}

/// A validated set result typed by element kind.
///
/// Each variant wraps a `HashSet` with concrete Rust types.
/// Callers that need a Python set invoke [`into_py_any`](ValidatedSet::into_py_any) explicitly.
#[derive(Clone)]
pub enum ValidatedSet {
    String(HashSet<String>),
    Float(HashSet<f64>),
    Int(HashSet<i64>),
    Bool(HashSet<bool>),
}

impl ValidatedSet {
    fn len(&self) -> usize {
        match self {
            ValidatedSet::String(v) => v.len(),
            ValidatedSet::Float(v) => v.len(),
            ValidatedSet::Int(v) => v.len(),
            ValidatedSet::Bool(v) => v.len(),
        }
    }

    /// Convert into a Python `set` via [`PySet::new`].
    pub fn into_py_any(self, py: Python) -> Bound<PySet> {
        match self {
            ValidatedSet::String(v) => PySet::new(py, &v).unwrap(),
            ValidatedSet::Float(v) => PySet::new(py, &v).unwrap(),
            ValidatedSet::Int(v) => PySet::new(py, &v).unwrap(),
            ValidatedSet::Bool(v) => PySet::new(py, &v).unwrap(),
        }
    }
}

/// A validated list result typed by element kind.
///
/// Each variant wraps a `Vec` with concrete Rust types.
/// Callers that need a Python list invoke [`into_py_any`](ValidatedList::into_py_any) explicitly.
#[derive(Clone)]
pub enum ValidatedList {
    String(Vec<String>),
    Float(Vec<f64>),
    Int(Vec<i64>),
    Bool(Vec<bool>),
}
impl ValidatedList {
    fn len(&self) -> usize {
        match self {
            ValidatedList::String(v) => v.len(),
            ValidatedList::Float(v) => v.len(),
            ValidatedList::Int(v) => v.len(),
            ValidatedList::Bool(v) => v.len(),
        }
    }

    /// Convert into a Python `list` via [`PyList::new`].
    pub fn into_py_any(self, py: Python) -> Bound<PyList> {
        match self {
            ValidatedList::String(v) => PyList::new(py, &v).unwrap(),
            ValidatedList::Float(v) => PyList::new(py, &v).unwrap(),
            ValidatedList::Int(v) => PyList::new(py, &v).unwrap(),
            ValidatedList::Bool(v) => PyList::new(py, &v).unwrap(),
        }
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

    pub fn validate_list_inner<T: DeserializeOwned>(
        &self,
        text: &str,
        length: Option<usize>,
        fix: bool,
    ) -> Option<Vec<T>> {
        let val = Self::deserialize::<Vec<T>>(text, fix).ok()?;

        let len = val.len();
        if let Some(l) = length
            && l != 0
            && len != l
        {
            warn!("length mismatch - expected {:?}, got {}", length, len);
            return None;
        }
        Some(val)
    }

    pub fn validate_set_inner<T: DeserializeOwned + Eq + Hash>(
        &self,
        text: &str,
        length: Option<usize>,
        fix: bool,
    ) -> Option<HashSet<T>> {
        let val = Self::deserialize::<HashSet<T>>(text, fix).ok()?;
        let len = val.len();
        if let Some(l) = length
            && l != 0
            && len != l
        {
            warn!("length mismatch - expected {:?}, got {}", length, len);
            return None;
        }
        Some(val)
    }

    pub fn validate_dict_inner<K: DeserializeOwned + Eq + Hash, V: DeserializeOwned>(
        &self,
        text: &str,
        length: Option<usize>,
        fix: bool,
    ) -> Option<HashMap<K, V>> {
        let val = Self::deserialize::<HashMap<K, V>>(text, fix).ok()?;
        let len = val.len();
        if let Some(l) = length
            && l != 0
            && len != l
        {
            warn!("length mismatch - expected {:?}, got {}", length, len);
            return None;
        }
        Some(val)
    }

    /// Validates that the text parses to a typed dictionary.
    ///
    /// Returns a [`ValidatedDict`] variant whose inner `HashMap` types are
    /// determined by `key_type` / `value_type`. Callers that need a Python
    /// object call [`ValidatedDict::into_py_any`] explicitly.
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     key_type: The type of dictionary keys.
    ///     value_type: The type of dictionary values.
    ///     length: Optional exact length requirement.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The validated dictionary or None if deserialization or length check fails.
    pub fn validate_dict_kv_inner(
        &self,
        text: &str,
        key_type: ValueType,
        value_type: ValueType,
        length: Option<usize>,
        fix: bool,
    ) -> Option<ValidatedDict> {
        match (key_type, value_type) {
            (ValueType::String, ValueType::String) => self
                .validate_dict_inner::<String, String>(text, length, fix)
                .map(ValidatedDict::StringString),
            (ValueType::String, ValueType::Float) => self
                .validate_dict_inner::<String, f64>(text, length, fix)
                .map(ValidatedDict::StringFloat),
            (ValueType::String, ValueType::Int) => self
                .validate_dict_inner::<String, i64>(text, length, fix)
                .map(ValidatedDict::StringInt),
            (ValueType::String, ValueType::Bool) => self
                .validate_dict_inner::<String, bool>(text, length, fix)
                .map(ValidatedDict::StringBool),
            (ValueType::Int, ValueType::String) => self
                .validate_dict_inner::<i64, String>(text, length, fix)
                .map(ValidatedDict::IntString),
            (ValueType::Int, ValueType::Float) => self
                .validate_dict_inner::<i64, f64>(text, length, fix)
                .map(ValidatedDict::IntFloat),
            (ValueType::Int, ValueType::Int) => self
                .validate_dict_inner::<i64, i64>(text, length, fix)
                .map(ValidatedDict::IntInt),
            (ValueType::Int, ValueType::Bool) => self
                .validate_dict_inner::<i64, bool>(text, length, fix)
                .map(ValidatedDict::IntBool),
            (ValueType::Bool, ValueType::String) => self
                .validate_dict_inner::<bool, String>(text, length, fix)
                .map(ValidatedDict::BoolString),
            (ValueType::Bool, ValueType::Float) => self
                .validate_dict_inner::<bool, f64>(text, length, fix)
                .map(ValidatedDict::BoolFloat),
            (ValueType::Bool, ValueType::Int) => self
                .validate_dict_inner::<bool, i64>(text, length, fix)
                .map(ValidatedDict::BoolInt),
            (ValueType::Bool, ValueType::Bool) => self
                .validate_dict_inner::<bool, bool>(text, length, fix)
                .map(ValidatedDict::BoolBool),
            _ => panic!("Invalid type combination"),
        }
    }

    /// Validates that the text parses to a typed set.
    ///
    /// Returns a [`HashSet`] with concrete element type determined by
    /// `value_type`. Callers that need a Python set call
    /// [`validate_set`](JsonParser::validate_set) or convert via [`PySet::new`].
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     value_type: The type of set elements.
    ///     length: Optional exact length requirement.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The validated set or None if deserialization or length check fails.
    pub fn validate_set_v_inner(
        &self,
        text: &str,
        value_type: ValueType,
        length: Option<usize>,
        fix: bool,
    ) -> Option<ValidatedSet> {
        let val = match value_type {
            ValueType::String => {
                ValidatedSet::String(self.validate_set_inner::<String>(text, length, fix)?)
            }
            ValueType::Float => {
                // TODO
                panic!("validate_set_inner: float not supported")
            }
            ValueType::Int => ValidatedSet::Int(self.validate_set_inner::<i64>(text, length, fix)?),
            ValueType::Bool => {
                ValidatedSet::Bool(self.validate_set_inner::<bool>(text, length, fix)?)
            }
        };
        Some(val)
    }

    pub fn validate_list_v_inner(
        &self,
        text: &str,
        value_type: ValueType,
        length: Option<usize>,
        fix: bool,
    ) -> Option<ValidatedList> {
        let val = match value_type {
            ValueType::String => {
                ValidatedList::String(self.validate_list_inner::<String>(text, length, fix)?)
            }
            ValueType::Float => {
                ValidatedList::Float(self.validate_list_inner::<f64>(text, length, fix)?)
            }
            ValueType::Int => {
                ValidatedList::Int(self.validate_list_inner::<i64>(text, length, fix)?)
            }
            ValueType::Bool => {
                ValidatedList::Bool(self.validate_list_inner::<bool>(text, length, fix)?)
            }
        };

        Some(val)
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
    #[pyo3(signature=(text, elements_type, length=None, fix=true))]
    #[gen_stub(
        override_return_type(type_repr = "typing.List[_T]|None", imports = ("typing",))
    )]
    pub fn validate_list<'a>(
        &self,
        python: Python<'a>,
        text: &str,

        #[gen_stub(override_type(type_repr = "typing.Type[_T]"))] elements_type: Bound<'a, PyType>,
        length: Option<usize>,
        fix: bool,
    ) -> Option<Bound<'a, PyList>> {
        let value_type = ValueType::from_type(elements_type).ok()?;
        self.validate_list_v_inner(text, value_type, length, fix)
            .map(|v| v.into_py_any(python))
    }

    /// Validates that the text parses to a typed set and returns a Python set.
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     elements_type: The type of set elements.
    ///     length: Optional exact length requirement.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The validated Python set or None if validation fails.
    #[pyo3(signature=(text, elements_type, length=None, fix=true))]
    #[gen_stub(
        override_return_type(type_repr = "typing.Set[_T]|None", imports = ("typing",))
    )]
    pub fn validate_set<'a>(
        &self,
        python: Python<'a>,
        text: &str,

        #[gen_stub(override_type(type_repr = "typing.Type[_T]"))] elements_type: Bound<'a, PyType>,
        length: Option<usize>,
        fix: bool,
    ) -> PyResult<Option<Bound<'a, PySet>>> {
        let value_type = ValueType::from_type(elements_type)?;
        Ok(self
            .validate_set_v_inner(text, value_type, length, fix)
            .map(|v| v.into_py_any(python)))
    }

    /// Validates that the text parses to a typed dictionary and returns a Python dict.
    ///
    /// Args:
    ///     text: The text to parse as JSON.
    ///     key_type: The type of dictionary keys.
    ///     value_type: The type of dictionary values.
    ///     length: Optional exact length requirement.
    ///     fix: Whether to attempt JSON repair before parsing.
    ///
    /// Returns:
    ///     The validated Python dict or None if validation fails.
    #[pyo3(signature=(text, key_type,value_type,length=None, fix=true))]
    #[gen_stub(
        override_return_type(type_repr = "typing.Dict[_K,_V]|None", imports = ("typing",))
    )]
    pub fn validate_dict<'a>(
        &self,
        python: Python<'a>,
        text: &str,
        #[gen_stub(override_type(type_repr = "typing.Type[_K]"))] key_type: Bound<'a, PyType>,
        #[gen_stub(override_type(type_repr = "typing.Type[_V]"))] value_type: Bound<'a, PyType>,
        length: Option<usize>,
        fix: bool,
    ) -> PyResult<Option<Bound<'a, PyAny>>> {
        let key_type = ValueType::from_type(key_type)?;
        let value_type = ValueType::from_type(value_type)?;

        Ok(self
            .validate_dict_kv_inner(text, key_type, value_type, length, fix)
            .map(|v| v.into_py_any(python)))
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
#[derive(Clone)]
#[pyclass(get_all, from_py_object)]
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
        Self::with_separators(var_names::SNIPPET_LEFT_SEP, var_names::SNIPPET_RIGHT_SEP).unwrap()
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
        module_variable!("fabricatio_core.rust", stringify!(GENERIC_BLOCK_TYPE), String);
    }
);

pub static JSON_PARSER: Lazy<JsonParser> = Lazy::new(JsonParser::capture_json_codeblock);

pub static PYTHON_PARSER: Lazy<CodeBlockParser> = Lazy::new(CodeBlockParser::capture_python);

pub static GENERIC_PARSER: Lazy<GenericBlockParser> =
    Lazy::new(GenericBlockParser::capture_generic_string);

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
    m.add_class::<ValueType>()?;
    m.add(var_names::JSON_PARSER, JSON_PARSER.to_owned())?;
    m.add(var_names::PYTHON_PARSER, PYTHON_PARSER.to_owned())?;
    m.add(var_names::GENERIC_PARSER, GENERIC_PARSER.to_owned())?;
    m.add(var_names::SNIPPET_PARSER, SNIPPET_PARSER.to_owned())?;

    use var_names::GENERIC_BLOCK_TYPE;

    m.add(stringify!(GENERIC_BLOCK_TYPE), GENERIC_BLOCK_TYPE)?;

    Ok(())
}
