use crate::hbs_helpers::{getlang, hash, len, word_count};
use handlebars::{no_escape, Handlebars};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pythonize::depythonize;
use serde_json::Value;
use std::path::PathBuf;
use walkdir::WalkDir;

/// Python bindings for the TemplateManager struct.
#[pyclass]
pub struct TemplateManager {
    templates_dir: Vec<PathBuf>,
    handlebars: Handlebars<'static>,
    suffix: String,
}

#[pymethods]
impl TemplateManager {
    /// Create a new TemplateManager instance.
    #[new]
    #[pyo3(signature = (template_dirs, suffix=None, active_loading=None))]
    fn new(template_dirs: Vec<Bound<'_, PyAny>>, suffix: Option<String>, active_loading: Option<bool>) -> PyResult<Self> {
        // Convert Python paths to Rust PathBufs
        let templates_dir = template_dirs.into_iter()
            .map(|dir| dir.call_method0("as_posix")?.extract::<String>().map(PathBuf::from))
            .collect::<PyResult<Vec<PathBuf>>>()?;

        let mut handlebars = Handlebars::new();
        handlebars.set_dev_mode(active_loading.unwrap_or(false));
        handlebars.register_escape_fn(no_escape);

        let mut manager = Self {
            templates_dir,
            handlebars,
            suffix: suffix.unwrap_or_else(|| "hbs".to_string()),
        };

        manager.discover_templates();
        manager.register_builtin_helper();

        Ok(manager)
    }

    #[getter]
    fn template_count(&self) -> usize {
        self.handlebars.get_templates().len()
    }

    /// Discover the templates in the template directories.
    fn discover_templates(&mut self) {
        self.handlebars.clear_templates();

        self.discovered_templates_raw()
            .iter()
            .for_each(|path| {
                let name = path.file_stem().unwrap().to_str().unwrap();
                self.handlebars.register_template_file(name, path).unwrap();
            });
    }

    /// Get the source code of a template.
    fn get_template_source(&self, name: &str) -> Option<String> {
        self.discovered_templates_raw()
            .iter()
            .filter(|&path| path.file_stem().unwrap().to_string_lossy() == name)
            .map(|path| path.to_string_lossy().to_string())
            .last()
    }

    /// Render a template with the given data.
    fn render_template(&self, name: &str, data: &Bound<'_, PyDict>) -> PyResult<String> {
        depythonize::<Value>(data)
            .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
            .and_then(|json_data| self.handlebars.render(name, &json_data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e))))
    }

    fn render_template_raw(&self, template: &str, data: &Bound<'_, PyDict>) -> PyResult<String> {
        depythonize::<Value>(data)
            .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
            .and_then(|json_data| self.handlebars.render_template(template, &json_data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e))))
    }
}

impl TemplateManager {
    /// Returns a list of all discovered templates.
    fn discovered_templates_raw(&self) -> Vec<PathBuf> {
        self.templates_dir.iter().rev()
            .flat_map(|dir| {
                WalkDir::new(dir)
                    .into_iter()
                    .filter_map(Result::ok)
                    .filter(|e| e.file_type().is_file())
                    .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some(&self.suffix))
                    .map(|e| e.path().to_path_buf())
            })
            .collect()
    }


    fn register_builtin_helper(&mut self) {
        self.handlebars.register_helper("len", Box::new(len));
        self.handlebars.register_helper("getlang", Box::new(getlang));
        self.handlebars.register_helper("hash", Box::new(hash));
        self.handlebars.register_helper("word_count", Box::new(word_count))
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TemplateManager>()?;
    Ok(())
}