use mitex::convert_math;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::{wrap_pyfunction, Bound, PyResult, Python};
use regex::Regex;

/// convert the tex to typst
#[pyfunction]
fn tex_to_typst(string: &str) -> PyResult<String> {
    convert_math(string, None).map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
}

/// Helper function to convert TeX with a given pattern
fn convert_tex_with_pattern(pattern: &str, string: &str, block: bool) -> PyResult<String> {
    let re = Regex::new(pattern).map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("Regex error: {}", e)))?;

    let result = re.replace_all(string, |caps: &regex::Captures| {
        let tex_code = caps.get(1).unwrap().as_str();
        match convert_math(tex_code, None) {
            Ok(converted) => {
                if block {
                    format!("$\n{}\n$", converted)
                } else {
                    format!("${}$", converted)
                }
            }
            Err(e) => format!("Error converting {}: {}", tex_code, e),
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
    m.add_function(wrap_pyfunction!(tex_to_typst, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_inline_tex, m)?)?;
    m.add_function(wrap_pyfunction!(convert_all_block_tex, m)?)?;
    Ok(())
}
