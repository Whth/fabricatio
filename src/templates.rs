use handlebars::{Handlebars, RenderError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::Serialize;
use std::collections::HashMap;
use std::path::PathBuf;
use walkdir::WalkDir;
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyTemplateManager>()?;
    Ok(())
}


/// Python bindings for the TemplateManager struct.
#[pyclass]
#[pyo3(name = "TemplateManager")]
struct PyTemplateManager {
    manager: TemplateManager,
}

#[pymethods]
impl PyTemplateManager {
    /// Create a new TemplateManager instance.
    #[new]
    fn new(template_dirs: Vec<String>) -> Self {
        let template_dirs = template_dirs.into_iter().map(PathBuf::from).collect();
        PyTemplateManager {
            manager: TemplateManager::new(template_dirs),
        }
    }

    /// Get the path of a template by name.
    fn get_template_path(&self, name: &str) -> Option<String> {
        self.manager.get_template_path(name).map(|path| path.to_string_lossy().into_owned())
    }

    /// Render a template with the given data.
    fn render_template(&self, name: &str, data: &Bound<'_, PyDict>) -> PyResult<String> {
        let data: HashMap<String, String> = data.extract()?;
        self.manager.render_template(name, &data).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }
}

pub struct TemplateManager {
    templates_dir: Vec<PathBuf>,
    discovered_templates: HashMap<String, PathBuf>,
    handlebars: Handlebars<'static>,
}

impl TemplateManager {
    pub fn new(template_dirs: Vec<PathBuf>) -> Self {
        let mut manager = TemplateManager {
            templates_dir: template_dirs,
            discovered_templates: HashMap::new(),
            handlebars: Handlebars::new(),
        };
        manager.discover_templates();
        manager
    }

    pub fn discover_templates(&mut self) {
        let mut discovered = HashMap::new();

        for dir in self.templates_dir.iter().rev() {
            for entry in WalkDir::new(dir)
                .into_iter()
                .filter_map(|e| e.ok())
                .filter(|e| e.file_type().is_file())
            {
                let path = entry.path();
                if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                    discovered.insert(stem.to_string(), path.to_path_buf());
                }
            }
        }

        self.discovered_templates = discovered;
        println!("Discovered {} templates.", self.discovered_templates.len());
    }

    pub fn get_template_path(&self, name: &str) -> Option<&PathBuf> {
        self.discovered_templates.get(name)
    }

    pub fn render_template<T>(&self, name: &str, data: &T) -> Result<String, RenderError>
    where
        T: Serialize,
    {
        if let Some(path) = self.get_template_path(name) {
            let template = std::fs::read_to_string(path)?;
            self.handlebars.render_template(&template, data)
        } else {
            Err(RenderError::strict_error(Some(&"Template not found".to_string())))
        }
    }
}
