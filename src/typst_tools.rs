use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::{wrap_pyfunction, Bound, PyResult, Python};
use pythonize::{depythonize, pythonize};
use regex::Regex;
use serde_yml::Value;
use tex2typst_rs::tex2typst;

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

/// convert the tex to typst
#[pyfunction]
fn tex_to_typst(string: &str) -> PyResult<String> {
    tex2typst(string).map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))
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
/// Helper function to convert TeX with a given pattern
fn convert_tex_with_pattern(pattern: &str, string: &str, block: bool) -> PyResult<String> {
    let re = Regex::new(pattern).map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("Regex error: {}", e)))
        .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))?;


    let result = re.replace_all(string, |caps: &regex::Captures| {
        let tex_code = caps.get(1).unwrap().as_str();
        match tex2typst(tex_code) {
            Ok(converted) => {
                if block {
                    format!("$\n{}\n{}\n$", comment(tex_code.trim()), converted)
                } else {
                    format!(" ${}$ ", converted)
                }
            }

            Err(e) => if block {
                format!("$\n{}\n\"{}\"\n$", comment(tex_code), e)
            } else {
                format!(" ${}$ ", tex_code)
            },
        }
    });

    Ok(result.to_string())
}


#[pyfunction]
fn convert_all_inline_tex(string: &str) -> PyResult<String> {
    convert_tex_with_pattern(r"\\\((.*?)\\\)", string, false)
}


#[pyfunction]
fn convert_all_block_tex(string: &str) -> PyResult<String> {
    convert_tex_with_pattern(r"(?s)\\\[(.*?)\\]", string, true)
}

#[pyfunction]
/// A func to fix labels in a string.
pub fn fix_misplaced_labels(string: &str) -> String {
    // Match \[ ... \] blocks, non-greedy matching for the content inside
    let block_re = Regex::new(r#"(?s)\\\[(.*?)\\]"#).unwrap();
    // Match label format <...>
    let label_re = Regex::new(r#"(?s)<[a-zA-Z0-9\-]*>"#).unwrap();

    block_re.replace_all(string, move |caps: &regex::Captures| {
        let content = caps.get(1).unwrap().as_str();
        // Extract all labels and concatenate them into a single string
        let labels_str = label_re.find_iter(content)
            .map(|mat| mat.as_str())
            .collect::<String>();
        // Remove labels from the content
        let new_content = label_re.replace_all(content, "").to_string();
        // Construct the new block: [new content] + labels
        format!("\\[{}\\]", new_content) + &labels_str
    }).into_owned()
}

/// Split out metadata from a string
#[pyfunction]
fn split_out_metadata<'a>(python: Python<'a>, string: &str) -> (Option<Bound<'a, PyAny>>, String) {
    let metadata = string.lines()
        .take_while(|line| line.starts_with("//"))
        .collect::<Vec<&str>>()
        .join("\n");

    if let Ok(value) = serde_yml::from_str::<Value>(metadata.uncomment().as_str()) {
        (Some(pythonize(python, &value).unwrap()), string.strip_prefix(metadata.as_str()).unwrap().into())
    } else {
        (None, string.to_string())
    }
}


/// Convert a Python object to a YAML string.
#[pyfunction]
fn to_metadata(data: &Bound<'_, PyAny>) -> PyResult<String> {
    depythonize::<Value>(data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(
            |value| {
                serde_yml::to_string(&value).map_err(|e| PyRuntimeError::new_err(e.to_string())).map(|s| s.comment())
            }
        )
}


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(comment, m)?)?;
    m.add_function(wrap_pyfunction!(uncomment, m)?)?;

    m.add_function(wrap_pyfunction!(tex_to_typst, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_inline_tex, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_block_tex, m)?)?;


    m.add_function(wrap_pyfunction!(fix_misplaced_labels, m)?)?;
    m.add_function(wrap_pyfunction!(split_out_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(to_metadata, m)?)?;
    Ok(())
}

