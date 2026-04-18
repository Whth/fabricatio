use deck_loader::loader::{AnkiDeckLoader, constants};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pythonize::depythonize;

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use serde_yaml2::wrapper::YamlNodeWrapper;
use std::fs;
use std::path::PathBuf;

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Compiles an Anki deck from a path to an output file.
///
/// Args:
///     path: The path to the Anki deck.
///     output: The output file path.
///
/// Returns:
///     PyResult<()> indicating success.
fn compile_deck(path: PathBuf, output: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(path)
        .export_deck(output)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?;
    Ok(())
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Creates a new Anki deck project with the given configuration.
///
/// Args:
///     path: The directory path for the project.
///     deck_name: Optional name for the deck.
///     deck_description: Optional description for the deck.
///     author: Optional author name.
///     model_name: Optional model name.
///     fields: Optional list of field names.
///
/// Returns:
///     PyResult<()> indicating success.
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

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Saves metadata to a YAML file in the specified directory.
///
/// Args:
///     dir_path: The directory path.
///     name: The name for the metadata file (without extension).
///     data: The Python object to serialize as YAML.
///
/// Returns:
///     PyResult<()> indicating success.
fn save_metadata(dir_path: PathBuf, name: String, data: Bound<'_, PyAny>) -> PyResult<()> {
    fs::create_dir_all(&dir_path)?;
    depythonize::<YamlNodeWrapper>(&data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(|value| {
            let content =
                serde_yaml2::to_string(value).map_err(|e| PyRuntimeError::new_err(e.to_string()));
            content.and_then(|content| {
                let path = dir_path.join(format!("{}.yaml", name));
                fs::write(path, content).map_err(|e| PyRuntimeError::new_err(e.to_string()))
            })
        })
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Adds CSV data to an Anki deck project.
///
/// Args:
///     project_path: The path to the Anki deck project.
///     model_name: The name of the model to add data to.
///     data: The path to the CSV file.
///
/// Returns:
///     PyResult<()> indicating success.
fn add_csv_data(project_path: PathBuf, model_name: &str, data: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(project_path)
        .add_csv_data(model_name, &data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Saves Anki card templates (front, back, and optional CSS) to files.
///
/// Args:
///     dir_path: The directory to save templates in.
///     front: The front template content.
///     back: The back template content.
///     css: Optional CSS content.
///
/// Returns:
///     PyResult<()> indicating success.
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
/// Args:
///     html: The HTML content to search within.
///     tag: The name of the HTML tag whose content needs to be extracted.
///
/// Returns:
///     A concatenated string of all contents found between the opening and closing tags.
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
/// Args:
///     html: The full HTML content.
///
/// Returns:
///     A tuple containing (layout, javascript_content, css_content).
///     - layout: HTML content without script and style sections
///     - javascript_content: Extracted from script tags
///     - css_content: Extracted from style tags
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
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

/// Registers the Anki deck functions with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_deck, m)?)?;
    m.add_function(wrap_pyfunction!(create_deck_project, m)?)?;
    m.add_function(wrap_pyfunction!(save_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(save_template, m)?)?;
    m.add_function(wrap_pyfunction!(add_csv_data, m)?)?;
    m.add_function(wrap_pyfunction!(extract_html_component, m)?)?;
    Ok(())
}
