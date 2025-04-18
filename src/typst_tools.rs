use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::{wrap_pyfunction, Bound, PyResult, Python};
use regex::Regex;
use tex2typst_rs::tex2typst;


/// convert the tex to typst
#[pyfunction]
fn tex_to_typst(string: &str) -> PyResult<String> {
    tex2typst(string).map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))
}

/// add comment to the string
#[pyfunction]
fn comment(string: &str) -> String {
    string
        .split('\n')
        .map(|line| format!("// {}", line))
        .collect::<Vec<_>>()
        .join("\n")
}


/// remove comment from the string
#[pyfunction]
fn uncomment(string: &str) -> String {
    string
        .split('\n') // Split the string into lines
        .map(|line| {
            line.strip_prefix("// ")
                .or_else(|| line.strip_prefix("//"))
                .unwrap_or(line)
        })
        .collect::<Vec<_>>() // Collect the lines into a Vec<&str>
        .join("\n") // Join the lines back into a single string with newline characters
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
pub fn fix_misplaced_labels(input: &str) -> String {
    // Match \[ ... \] blocks, non-greedy matching for the content inside
    let block_re = Regex::new(r#"(?s)\\\[(.*?)\\]"#).unwrap();
    // Match label format <...>
    let label_re = Regex::new(r#"(?s)<[a-zA-Z0-9\-]*>"#).unwrap();

    block_re.replace_all(input, move |caps: &regex::Captures| {
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


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(comment, m)?)?;
    m.add_function(wrap_pyfunction!(uncomment, m)?)?;

    m.add_function(wrap_pyfunction!(tex_to_typst, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_inline_tex, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_block_tex, m)?)?;

    
    m.add_function(wrap_pyfunction!(fix_misplaced_labels, m)?)?;
    Ok(())
}
