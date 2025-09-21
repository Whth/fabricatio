use pyo3::prelude::*;
use regex::Regex;

mod novel;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    novel::register(python, m)?;
    m.add_function(wrap_pyfunction!(text_to_xhtml_paragraphs, m)?)?;
    Ok(())
}

#[pyfunction]
fn text_to_xhtml_paragraphs(source: &str) -> String {
    // Match one or more newlines as paragraph separators
    Regex::new(r"\n+")
        .unwrap()
        .split(source.trim())
        .map(|line| line.trim())
        .filter(|line| !line.is_empty())
        .map(|line| format!("<p>{}</p>", line))
        .collect::<Vec<_>>()
        .join("\n")
}
