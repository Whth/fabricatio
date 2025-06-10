use deck_loader::loader::{AnkiDeckLoader, constants};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pythonize::depythonize;
use serde_yml::Value;
use std::fs;
use std::path::PathBuf;

#[pyfunction]
fn compile_deck(path: PathBuf, output: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?
        .export_deck(output)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?;
    Ok(())
}

#[pyfunction]
fn create_deck_project(
    path: PathBuf,
    deck_name: Option<String>,
    deck_description: Option<String>,
    author: Option<String>,
    model_name: Option<String>,
    fields: Option<Vec<String>>,
) -> PyResult<()> {
    AnkiDeckLoader::create_project_template(
        path,
        deck_name,
        deck_description,
        author,
        model_name,
        fields,
    )
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?;
    Ok(())
}

#[pyfunction]
fn save_metadata(dir_path: PathBuf, name: String, data: Bound<'_, PyAny>) -> PyResult<()> {
    fs::create_dir_all(&dir_path)?;
    depythonize::<Value>(&data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(|value| {
            let content =
                serde_yml::to_string(&value).map_err(|e| PyRuntimeError::new_err(e.to_string()));
            content.and_then(|content| {
                let path = dir_path.join(format!("{}.yaml", name));
                fs::write(path, content).map_err(|e| PyRuntimeError::new_err(e.to_string()))
            })
        })
}

#[pyfunction]
fn add_csv_data(project_path: PathBuf, model_name: &str, data: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(project_path)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
        .add_csv_data(model_name, &data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature=(dir_path, front, back, css=None))]
fn save_template(
    dir_path: PathBuf,
    front: String,
    back: String,
    css: Option<String>,
) -> PyResult<()> {
    fs::create_dir_all(&dir_path)?;
    fs::write(dir_path.join(constants::TEMPLATE_FRONT), front)?;
    fs::write(dir_path.join(constants::TEMPLATE_BACK), back)?;
    if let Some(css) = css {
        fs::write(dir_path.join(constants::TEMPLATE_CSS), css)?;
    }

    Ok(())
}

/// Extracts content located within all occurrences of a specified HTML tag.
///
/// # Arguments
/// * `html` - A string slice containing the HTML content to search within.
/// * `tag` - The name of the HTML tag whose content needs to be extracted.
///
/// # Returns
/// A concatenated string of all contents found between the opening and closing of the specified tags.
fn extract_content_by_tag(html: &str, tag: &str) -> String {
    use regex::Regex;

    let pattern = format!(r"(?s)<{tag}[^>]*>(.*?)</{tag}>");
    let regex = Regex::new(&pattern).unwrap();
    regex
        .captures_iter(html)
        .map(|cap| cap.get(1).map_or("", |m| m.as_str()))
        .collect::<Vec<_>>()
        .join("\n")
}

/// Extracts JavaScript, CSS, and layout components from an HTML string.
///
/// # Arguments
/// * `html` - A string slice containing the full HTML content.
///
/// # Returns
/// A tuple with three strings:
/// 1. Layout (HTML content without script and style sections).
/// 2. JavaScript content (extracted from `<script>` tags).
/// 3. CSS content (extracted from `<style>` tags).
///
/// # Errors
/// This function wraps its return in `PyResult` but does not currently produce recoverable errors.
#[pyfunction]
fn extract_html_component(html: &str) -> PyResult<(String, String, String)> {
    use regex::Regex;

    // Extract JavaScript from <script> tags
    let js_content = extract_content_by_tag(html, "script");

    // Extract CSS from <style> tags
    let css_content = extract_content_by_tag(html, "style");

    // Remove script and style tags to get remaining HTML layout
    let script_regex = Regex::new(r"(?s)<script[^>]*>.*?</script>").unwrap();
    let style_regex = Regex::new(r"(?s)<style[^>]*>.*?</style>").unwrap();
    let mut layout = script_regex.replace_all(html, "").to_string();
    layout = style_regex.replace_all(&layout, "").to_string();

    Ok((layout, js_content, css_content))
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_deck, m)?)?;
    m.add_function(wrap_pyfunction!(create_deck_project, m)?)?;
    m.add_function(wrap_pyfunction!(save_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(save_template, m)?)?;
    m.add_function(wrap_pyfunction!(add_csv_data, m)?)?;
    m.add_function(wrap_pyfunction!(extract_html_component, m)?)?;
    Ok(())
}
