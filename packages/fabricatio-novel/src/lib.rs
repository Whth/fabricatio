#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use regex::Regex;

mod novel;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    novel::register(python, m)?;
    m.add_function(wrap_pyfunction!(text_to_xhtml_paragraphs, m)?)?;
    Ok(())
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
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

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
