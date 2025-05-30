use genanki_rs::{Deck, Field, Model, Note, Package, Template};
use pyo3::prelude::*;
use std::collections::HashMap;

#[pyclass]
struct DeckBuilder {
    deck: Option<Deck>,
    models: HashMap<i64, Model>,
}

#[pymethods]
impl DeckBuilder {
    #[new]
    fn new() -> Self {
        Self {
            deck: None,
            models: HashMap::new(),
        }
    }

    fn create_deck<'py>(mut slf: PyRefMut<'py, Self>, deck_id: i64, name: String, description: String) -> PyResult<PyRefMut<'py, Self>> {
        slf.deck = Some(Deck::new(deck_id, &name, &description));
        Ok(slf)
    }

    fn create_model<'py>(mut slf: PyRefMut<'py, Self>, model_id: i64, name: String, fields: Vec<String>, templates: Vec<(String, String, String)>, css: Option<String>) -> PyResult<PyRefMut<'py, Self>> {
        let model_fields: Vec<Field> = fields.into_iter().map(|f| Field::new(&f)).collect();
        let model_templates: Vec<Template> = templates.into_iter().map(|(name, qfmt, afmt)| {
            Template::new(&name).qfmt(&qfmt).afmt(&afmt)
        }).collect();

        let model = if let Some(css_path) = css {
            let css_content = std::fs::read_to_string(&css_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to read CSS file '{}': {}", css_path, e)))?;
            Model::new(model_id, &name, model_fields, model_templates).css(css_content)
        } else {
            Model::new(model_id, &name, model_fields, model_templates)
        };

        slf.models.insert(model_id, model);
        Ok(slf)
    }

    fn add_note<'py>(mut slf: PyRefMut<'py, Self>, model_id: i64, fields: Vec<String>) -> PyResult<PyRefMut<'py, Self>> {
        // Check if model exists first
        let model = slf.models.get(&model_id).cloned()
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Model not found"))?;

        // Check if deck exists and add note
        if let Some(ref mut deck) = slf.deck {
            let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();
            let note = Note::new(model, field_refs).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to create note: {:?}", e)))?;
            deck.add_note(note);
            Ok(slf)
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No deck created"))
        }
    }

    fn write_to_file(&mut self, filename: String) -> PyResult<()> {
        if let Some(deck) = self.deck.take() {
            deck.write_to_file(&filename).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write deck: {:?}", e)))?;
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No deck to write"))
        }
    }

    fn write_package_to_file(&mut self, filename: String, media_files: Vec<String>) -> PyResult<()> {
        if let Some(deck) = self.deck.take() {
            let media_refs: Vec<&str> = media_files.iter().map(|s| s.as_str()).collect();
            let mut package = Package::new(vec![deck], media_refs).map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to create package: {:?}", e)))?;
            package.write_to_file(&filename).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write package: {:?}", e)))?;
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No deck to write"))
        }
    }
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<DeckBuilder>()?;
    Ok(())
}