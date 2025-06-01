use deck_loader::loader::AnkiDeckLoader;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pythonize::depythonize;
use serde_yml::Value;
use std::path::{Path, PathBuf};

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
    depythonize::<Value>(&data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(|value| {
            let content =
                serde_yml::to_string(&value).map_err(|e| PyRuntimeError::new_err(e.to_string()));
            content.and_then(|content| {
                let path = dir_path.join(format!("{}.yaml", name));
                std::fs::write(path, content).map_err(|e| PyRuntimeError::new_err(e.to_string()))
            })
        })
}

fn save_card_type(dir_path: PathBuf) {}
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_deck, m)?)?;
    m.add_function(wrap_pyfunction!(create_deck_project, m)?)?;
    m.add_function(wrap_pyfunction!(save_metadata, m)?)?;
    Ok(())
}
