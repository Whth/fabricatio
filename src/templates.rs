use handlebars::Handlebars;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use std::path::PathBuf;
use walkdir::WalkDir;


/// Python bindings for the TemplateManager struct.
#[pyclass]
pub struct TemplateManager {
    templates_dir: Vec<PathBuf>,
    discovered_templates: HashMap<String, PathBuf>,
    handlebars: Handlebars<'static>,
    suffix: String,
}

#[pymethods]
impl TemplateManager {
    /// Create a new TemplateManager instance.
    #[new]
    #[pyo3(signature = (template_dirs, suffix=None))]
    fn new(template_dirs: Vec<Bound<'_, PyAny>>,suffix:Option<String>) -> PyResult<Self> {
        let template_dirs: Vec<PathBuf> = template_dirs
            .into_iter()
            .map(|dir| dir.call_method0("as_posix")?.extract::<String>().map(PathBuf::from))
            .collect::<PyResult<Vec<PathBuf>>>()?;

        let mut manager = TemplateManager {
            templates_dir: template_dirs,
            discovered_templates: HashMap::new(),
            handlebars: Handlebars::new(),
            suffix:suffix.unwrap_or("hbs".to_string()) 
        };
        manager.discover_templates();
        Ok(manager)
    }

    #[getter]
    fn template_count(&self) -> usize {
        self.discovered_templates.len()
    }


    #[getter]
    fn templates(&self) -> Vec<String> {
        self.discovered_templates.keys().cloned().collect()
    }


    /// Discover the templates in the template directories.
    fn discover_templates(&mut self) {
        let mut discovered = HashMap::new();

        for dir in self.templates_dir.iter().rev() {
            for entry in WalkDir::new(dir)
                .into_iter()
                .filter_map(|e| e.ok())
                .filter(|e| e.file_type().is_file())
                .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some(&self.suffix))
            {
                let path = entry.path();
                if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                    discovered.insert(stem.to_string(), path.to_path_buf());
                }
            }
        }

        self.discovered_templates = discovered;
    }

    fn get_template(&self, name: &str) -> PyResult<String> {
        if let Some(path) = self.discovered_templates.get(name) {
            let template = std::fs::read_to_string(path)?;
            Ok(template)
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Template not found".to_string(),
            ))
        }
    }


    fn get_template_source(&self, name: &str) -> PyResult<String> {
        if let Some(path) = self.discovered_templates.get(name) {
            Ok(path.to_string_lossy().to_string())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Template not found".to_string(),
            ))
        }
    }
    /// Render a template with the given data.
    fn render_template(&self, name: &str, data: &Bound<'_, PyDict>) -> PyResult<String> {
        let data: HashMap<String, String> = data.extract()?;
        if let Some(path) = self.discovered_templates.get(name) {
            let template = std::fs::read_to_string(path)?;
            self.handlebars
                .render_template(&template, &data)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Template not found".to_string(),
            ))
        }
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TemplateManager>()?;
    Ok(())
}