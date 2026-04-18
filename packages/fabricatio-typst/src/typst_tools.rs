use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use pythonize::{depythonize, pythonize};
use regex::Regex;
use serde_yaml2::wrapper::YamlNodeWrapper;
use tex2typst_rs::tex2typst;
use tex_convertor::convert_all_tex_math as conv_to_typst;

/// A trait to add and remove comments from a string-like type.
pub trait Commentable: AsRef<str> {
    /// Adds a comment prefix `//` to each line of the string.
    ///
    /// Returns:
    ///     A new string with `//` prepended to each line.
    fn comment(&self) -> String {
        self.as_ref()
            .lines() // Split the string into lines
            .map(|line| format!("// {}", line)) // Add `//` to each line
            .collect::<Vec<_>>() // Collect the lines into a Vec<String>
            .join("\n") // Join the lines back into a single string with newline characters
    }

    /// Removes the comment prefix `//` from each line of the string.
    ///
    /// Returns:
    ///     A new string with `//` or `// ` prefix removed from each line.
    fn uncomment(&self) -> String {
        self.as_ref()
            .lines() // Split the string into lines
            .map(|line| {
                line.strip_prefix("// ")
                    .or_else(|| line.strip_prefix("//"))
                    .unwrap_or(line) // Remove `//` or `// ` prefix if present
            })
            .collect::<Vec<_>>() // Collect the lines back into a Vec<&str>
            .join("\n") // Join the lines back into a single string with newline characters
    }
}

// Implement the `Commentable` trait for all types that implement `AsRef<str>`.
impl<T: AsRef<str>> Commentable for T {}

/// Converts a raw LaTeX string to Typst format.
///
/// Args:
///     string: The raw LaTeX string to convert.
///
/// Returns:
///     A PyResult containing the converted Typst string.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn tex_to_typst(string: &str) -> PyResult<String> {
    tex2typst(string).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

/// Adds comment prefix `//` to each line of the string.
///
/// Args:
///     string: The input string to comment.
///
/// Returns:
///     A string with `//` prepended to each line.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn comment(string: &str) -> String {
    string.comment()
}

/// Removes comment prefix `//` from each line of the string.
///
/// Args:
///     string: The input string to uncomment.
///
/// Returns:
///     A string with comment prefixes removed from each line.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn uncomment(string: &str) -> String {
    string.uncomment()
}

/// Removes leading and trailing comment lines from a multi-line string.
///
/// Args:
///     string: The input string to strip comments from.
///
/// Returns:
///     A string with leading and trailing comment lines removed.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
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

/// Converts all supported TeX math expressions in a string to Typst format.
///
/// Handles $...$, $$...$$, \(...\), and \[...\] delimiters.
///
/// Args:
///     string: The input string containing TeX math expressions.
///
/// Returns:
///     A PyResult containing the string with converted math expressions.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn convert_all_tex_math(string: &str) -> PyResult<String> {
    conv_to_typst(string).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

/// Fixes misplaced labels in a string by moving them outside display math blocks.
///
/// Labels in the format <label> that appear inside \[...\] blocks are moved
/// to outside the block.
///
/// Args:
///     string: The input string to fix.
///
/// Returns:
///     A string with misplaced labels moved outside display math blocks.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
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

/// Splits metadata (YAML front matter) from a Typst document string.
///
/// Extracts leading comment lines as YAML metadata and returns the remaining content.
///
/// Args:
///     python: The Python interpreter instance.
///     string: The input string with potential YAML front matter.
///
/// Returns:
///     A tuple of (parsed metadata as Python object or None, remaining string content).
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn split_out_metadata<'a>(python: Python<'a>, string: &str) -> (Option<Bound<'a, PyAny>>, String) {
    let metadata = string
        .lines()
        .take_while(|line| line.starts_with("//"))
        .collect::<Vec<&str>>()
        .join("\n");

    if let Ok(value) = serde_yaml2::from_str::<YamlNodeWrapper>(metadata.uncomment().as_str()) {
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

/// Converts a Python object to a YAML string with comment formatting.
///
/// Args:
///     data: The Python object to convert.
///
/// Returns:
///     A PyResult containing the YAML string with `//` comments.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn to_metadata(data: &Bound<'_, PyAny>) -> PyResult<String> {
    depythonize::<YamlNodeWrapper>(data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(|value| {
            serde_yaml2::to_string(&value)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))
                .map(|s| s.comment())
        })
}

/// Replaces the body content enclosed by two wrapper strings.
///
/// Args:
///     string: The original string containing the wrapped body.
///     wrapper: The wrapper string that marks the beginning and end.
///     new_body: The new body content to insert.
///
/// Returns:
///     The string with the body replaced, or None if wrapper not found.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn replace_thesis_body(string: &str, wrapper: &str, new_body: &str) -> Option<String> {
    // Perform direct string replacement
    Some(string.replace(&extract_body(string, wrapper)?, &new_body))
}

/// Extracts the body content enclosed by exactly two wrapper strings.
///
/// Args:
///     string: The string containing the wrapped body.
///     wrapper: The wrapper string that marks the beginning and end.
///
/// Returns:
///     The body content if exactly one match found, None otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn extract_body(string: &str, wrapper: &str) -> Option<String> {
    // Escape the wrapper string for regex safety
    let escaped_wrapper = regex::escape(wrapper);

    // Construct regex pattern to capture content between wrappers
    let pattern = format!(r"(?s){}(.*?){}", escaped_wrapper, escaped_wrapper);
    let re = Regex::new(&pattern).ok()?; // Return None if regex fails

    // Extract matches and return None if more than one match found
    let mut matches = re.captures_iter(string);
    let first_match = matches.next()?;

    // If there's a second match, return None
    if matches.next().is_some() {
        return None;
    }

    // Return the first captured group (the body content)
    first_match.get(1).map(|m| m.as_str().to_string())
}

/// Extracts sections from markdown-style text by header level.
///
/// Args:
///     string: The markdown text to parse.
///     level: The header level to extract (e.g., 1 for #, 2 for ##).
///     section_char: Optional character to use as header marker (default: #).
///
/// Returns:
///     A list of tuples containing (header_text, section_content).
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature=(string, level=1, section_char="#"))]
fn extract_sections(
    string: &str,
    level: usize,
    section_char: Option<&str>,
) -> PyResult<Vec<(String, String)>> {
    let section_char = section_char.unwrap_or("#");

    // Build the header prefix: section_char repeated `level` times followed by space
    // e.g., for level=1 with "#": "# " ; for level=2 with "=": "== "
    let header_prefix = section_char.repeat(level);

    let mut results = Vec::new();
    let mut current_header = String::new();
    let mut current_content = String::new();
    let mut in_section = false;

    for line in string.lines() {
        let trimmed = line.trim();
        // Check if line starts with header_prefix followed by whitespace (or is exactly the prefix)
        if trimmed.starts_with(&header_prefix) {
            let rest = &trimmed[header_prefix.len()..];
            if rest.is_empty() || rest.starts_with(' ') {
                // Save previous section if exists
                if in_section && !current_header.is_empty() {
                    results.push((current_header.clone(), current_content.trim().to_string()));
                }
                // Start new section
                current_header = rest.trim().to_string();
                current_content.clear();
                in_section = true;
                continue;
            }
        }
        if in_section {
            if !current_content.is_empty() {
                current_content.push('\n');
            }
            current_content.push_str(trimmed);
        }
    }

    // Don't forget the last section
    if in_section && !current_header.is_empty() {
        results.push((current_header, current_content.trim().to_string()));
    }

    Ok(results)
}

/// Registers the Typst utility functions with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
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
    m.add_function(wrap_pyfunction!(extract_sections, m)?)?;
    Ok(())
}
