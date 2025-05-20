use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::{wrap_pyfunction, Bound, PyResult, Python};
use pythonize::{depythonize, pythonize};
use regex::Regex;
use serde_yml::Value;
use tex2typst_rs::tex2typst;
use typst_conversion::convert_all_tex_math as conv_to_typst;

/// A trait to add and remove comments from a string-like type.
pub trait Commentable: AsRef<str> {
    /// Adds a comment (`//`) to each line of the string.
    fn comment(&self) -> String {
        self.as_ref()
            .lines() // Split the string into lines
            .map(|line| format!("// {}", line)) // Add `//` to each line
            .collect::<Vec<_>>() // Collect the lines into a Vec<String>
            .join("\n") // Join the lines back into a single string with newline characters
    }

    /// Removes comments (`//`) from each line of the string.
    fn uncomment(&self) -> String {
        self.as_ref()
            .lines() // Split the string into lines
            .map(|line| {
                line.strip_prefix("// ")
                    .or_else(|| line.strip_prefix("//"))
                    .unwrap_or(line) // Remove `//` or `// ` prefix if present
            })
            .collect::<Vec<_>>() // Collect the lines into a Vec<&str>
            .join("\n") // Join the lines back into a single string with newline characters
    }
}

// Implement the `Commentable` trait for all types that implement `AsRef<str>`.
impl<T: AsRef<str>> Commentable for T {}

/// convert a raw tex string to typst
#[pyfunction]
fn tex_to_typst(string: &str) -> PyResult<String> {
    tex2typst(string).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

/// add comment to the string
#[pyfunction]
fn comment(string: &str) -> String {
    string.comment()
}

/// remove comment from the string
#[pyfunction]
fn uncomment(string: &str) -> String {
    string.uncomment()
}

/// Removes leading and trailing comment lines from a multi-line string.
#[pyfunction]
fn strip_comment(string: &str) -> String {
    let lines: Vec<&str> = string.lines().collect();
    let mut start = 0;
    let mut end = lines.len();

    // Find the first non-comment line
    while start < lines.len() && lines[start].trim_start().starts_with("//") {
        start += 1;
    }

    // Find the last non-comment line
    while end > start && lines[end - 1].trim_start().starts_with("//") {
        end -= 1;
    }

    // Join the relevant lines back into a single string
    lines[start..end].join("\n")
}


/// Unified function to convert all supported TeX math expressions in a string to Typst format.
/// Handles $...$, $$...$$, \(...\), and \[...\].
#[pyfunction]
fn convert_all_tex_math(string: &str) -> PyResult<String> {
    conv_to_typst(string).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
/// A func to fix labels in a string.
pub fn fix_misplaced_labels(string: &str) -> String {
    // Match \[ ... \] blocks, non-greedy matching for the content inside
    let block_re = Regex::new(r#"(?s)\\\[(.*?)\\]"#).unwrap();
    // Match label format <...>
    let label_re = Regex::new(r#"(?s)<[a-zA-Z0-9\-]*>"#).unwrap();

    block_re
        .replace_all(string, move |caps: &regex::Captures| {
            let content = caps.get(1).unwrap().as_str();
            // Extract all labels and concatenate them into a single string
            let labels_str = label_re
                .find_iter(content)
                .map(|mat| mat.as_str())
                .collect::<String>();
            // Remove labels from the content
            let new_content = label_re.replace_all(content, "").to_string();
            // Construct the new block: [new content] + labels
            format!("\\[{}\\]", new_content) + &labels_str
        })
        .into_owned()
}

/// Split out metadata from a string
#[pyfunction]
fn split_out_metadata<'a>(python: Python<'a>, string: &str) -> (Option<Bound<'a, PyAny>>, String) {
    let metadata = string
        .lines()
        .take_while(|line| line.starts_with("//"))
        .collect::<Vec<&str>>()
        .join("\n");

    if let Ok(value) = serde_yml::from_str::<Value>(metadata.uncomment().as_str()) {
        (
            Some(pythonize(python, &value).unwrap()),
            string
                .strip_prefix(metadata.as_str())
                .unwrap_or(string)
                .into(),
        )
    } else {
        (None, string.to_string())
    }
}

/// Convert a Python object to a YAML string.
#[pyfunction]
fn to_metadata(data: &Bound<'_, PyAny>) -> PyResult<String> {
    depythonize::<Value>(data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(|value| {
            serde_yml::to_string(&value)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))
                .map(|s| s.comment())
        })
}

#[pyfunction]
fn replace_thesis_body(string: &str, wrapper: &str, new_body: &str) -> Option<String> {
    // Escape the wrapper string to handle special regex characters safely
    let escaped_wrapper = regex::escape(wrapper);

    // Count wrapper occurrences
    let count_re = Regex::new(&escaped_wrapper).ok()?; // Return None if regex fails
    let count = count_re.find_iter(string).count();
    if count != 2 {
        // Return None when wrapper count is not exactly 2
        return None;
    }

    // Construct the regex pattern to find content enclosed by the wrapper
    let pattern = format!(r"(?s){}(.*?){}", escaped_wrapper, escaped_wrapper);
    let re = Regex::new(&pattern).ok()?; // Return None if regex fails

    // Replace the old content with the new content
    let result = re
        .replace_all(string, |_caps: &regex::Captures| {
            format!("{}{}{}", wrapper, new_body, wrapper)
        })
        .into_owned();

    Some(result) // Wrap result in Some
}

// Implement extract_body to find content enclosed by exactly two wrappers
#[pyfunction]
fn extract_body(string: &str, wrapper: &str) -> Option<String> {
    // Escape the wrapper string for regex safety
    let escaped_wrapper = regex::escape(wrapper);

    // Count wrapper occurrences
    let count_re = Regex::new(&escaped_wrapper).ok()?; // Return None if regex fails
    let count = count_re.find_iter(string).count();
    if count != 2 {
        // Return None when wrapper count is not exactly 2
        return None;
    }

    // Construct regex pattern to capture content between wrappers
    let pattern = format!(r"(?s){}(.*?){}", escaped_wrapper, escaped_wrapper);
    let re = Regex::new(&pattern).ok()?; // Return None if regex fails

    // Extract and return the first captured group (the body content)
    re.captures_iter(string)
        .filter_map(|caps| caps.get(1).map(|m| m.as_str().to_string()))
        .next()
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(comment, m)?)?;
    m.add_function(wrap_pyfunction!(uncomment, m)?)?;

    m.add_function(wrap_pyfunction!(tex_to_typst, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_tex_math, m)?)?;

    m.add_function(wrap_pyfunction!(fix_misplaced_labels, m)?)?;
    m.add_function(wrap_pyfunction!(split_out_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(to_metadata, m)?)?;

    m.add_function(wrap_pyfunction!(replace_thesis_body, m)?)?;
    m.add_function(wrap_pyfunction!(extract_body, m)?)?;
    m.add_function(wrap_pyfunction!(strip_comment, m)?)?;
    Ok(())
}

