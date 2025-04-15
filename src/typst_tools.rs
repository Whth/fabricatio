use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::{wrap_pyfunction, Bound, PyResult, Python};
use regex::Regex;
use tex2typst_rs::tex2typst;


/// convert the tex to typst
#[pyfunction]
fn tex_to_typst(string: &str) -> PyResult<String> {
    tex2typst(string).map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
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
    let re = Regex::new(pattern).map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("Regex error: {}", e)))?;

    let result = re.replace_all(string, |caps: &regex::Captures| {
        let tex_code = caps.get(1).unwrap().as_str();
        match tex2typst(tex_code) {
            Ok(converted) => {
                if block {
                    format!("$\n{}\n{}\n$", comment(tex_code), converted)
                } else {
                    format!("${}$", converted)
                }
            }
            Err(e) => format!("Error converting `{}` to `{}`", tex_code, e),
        }
    });

    Ok(result.to_string())
}


#[pyfunction]
fn convert_all_inline_tex(string: &str) -> PyResult<String> {
    convert_tex_with_pattern(r"(?s)\$(.*?)\$", string, false)
}


#[pyfunction]
fn convert_all_block_tex(string: &str) -> PyResult<String> {
    convert_tex_with_pattern(r"(?s)\$\$(.*?)\$\$", string, true)
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(comment, m)?)?;
    m.add_function(wrap_pyfunction!(uncomment, m)?)?;

    m.add_function(wrap_pyfunction!(tex_to_typst, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_inline_tex, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_block_tex, m)?)?;

    Ok(())
}
