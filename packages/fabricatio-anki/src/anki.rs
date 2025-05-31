use deck_loader::loader::AnkiDeckLoader;
use pyo3::prelude::*;
use std::path::PathBuf;

#[pyfunction]
fn compile_deck(path: PathBuf, output: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(path).map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?
        .export_deck(output)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?
    ;
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


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_deck, m)?)?;
    m.add_function(wrap_pyfunction!(create_deck_project, m)?)?;
    Ok(())
}