use crate::config::Config;
use crate::hbs_helpers::{block, getlang, hash, len, word_count};
use handlebars::{no_escape, Handlebars};
use log::debug;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use pythonize::depythonize;
use rayon::prelude::*;
use serde_json::Value;
use std::path::PathBuf;
use walkdir::WalkDir;

/// Python bindings for the TemplateManager struct.
#[pyclass]
pub struct TemplateManager {
    #[pyo3(get, set)]
    templates_dir: Vec<PathBuf>,
    handlebars: Handlebars<'static>,
    suffix: String,
}

#[pymethods]
impl TemplateManager {
    /// Create a new TemplateManager instance.

    #[getter]
    fn template_count(&self) -> usize {
        self.handlebars.get_templates().len()
    }

    /// Discover the templates in the template directories.
    fn discover_templates(&mut self) {
        self.handlebars.clear_templates();

        self.discovered_templates_raw().iter().for_each(|path| {
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
            .next_back()
    }

    /// Render a template with the given data.
    fn render_template<'a>(
        &self,
        py: Python<'a>,
        name: &str,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        if data.is_instance_of::<PyList>() {
            debug!("Rendering list of templates");
            depythonize::<Vec<Value>>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
                .and_then(|seq| {
                    let rendered = seq
                        .iter()
                        .map(|item| {
                            self.handlebars.render(name, item).expect(
                                format!("Rendering error for {name} when rendering {item}")
                                    .as_str(),
                            )
                        })
                        .collect::<Vec<String>>();

                    Ok(PyList::new(py, rendered)
                        .expect("Failed to create PyList")
                        .as_any())
                        .cloned()
                })
        } else {
            debug!("Rendering single template");
            depythonize::<Value>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
                .and_then(|json_data| {
                    Ok(PyString::new(
                        py,
                        self.handlebars
                            .render(name, &json_data)
                            .expect(
                                format!("Rendering error for {name} when rendering {json_data}")
                                    .as_str(),
                            )
                            .as_str(),
                    )
                        .as_any())
                        .cloned()
                })
        }
    }

    fn render_template_raw<'a>(
        &self,
        py: Python<'a>,
        template: &str,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        if data.is_instance_of::<PyList>() {
            depythonize::<Vec<Value>>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
                .and_then(|seq| {
                    let rendered = seq
                        .iter()
                        .par_bridge()
                        .map(|item| {
                            self.handlebars.render_template(template, item).expect(
                                format!("Rendering error for {template} when rendering {item}")
                                    .as_str(),
                            )
                        })
                        .collect::<Vec<String>>();

                    Ok(PyList::new(py, &rendered)
                        .expect("Failed to create PyList")
                        .as_any())
                        .cloned()
                })
        } else {
            depythonize::<Value>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
                .and_then(|json_data| {
                    Ok(PyString::new(
                        py,
                        self.handlebars
                            .render_template(template, &json_data)
                            .unwrap_or_else(|_| {
                                panic!("Rendering error for {template} when rendering {json_data}")
                            })
                            .as_str(),
                    )
                        .as_any())
                        .cloned()
                })
        }
    }
}

impl TemplateManager {
    fn new(
        template_dir: Vec<PathBuf>,
        suffix: Option<String>,
        active_loading: Option<bool>,
    ) -> Self {
        // Convert Python paths to Rust PathBufs

        let mut handlebars = Handlebars::new();
        handlebars.set_dev_mode(active_loading.unwrap_or(false));
        handlebars.register_escape_fn(no_escape);

        let mut manager = Self {
            templates_dir: template_dir,
            handlebars,
            suffix: suffix.unwrap_or_else(|| "hbs".to_string()),
        };

        manager.discover_templates();
        manager.register_builtin_helper();

        manager
    }

    /// Returns a list of all discovered templates.
    fn discovered_templates_raw(&self) -> Vec<PathBuf> {
        self.templates_dir
            .iter()
            .rev()
            .flat_map(|dir| {
                WalkDir::new(dir)
                    .into_iter()
                    .filter_map(Result::ok)
                    .filter(|e| e.file_type().is_file())
                    .filter(|e| {
                        e.path().extension().and_then(|s| s.to_str()) == Some(self.suffix.as_str())
                    })
                    .map(|e| e.path().to_path_buf())
            })
            .inspect(|path| {
                debug!(
                    "Discovered template: {}=>{}",
                    path.file_stem().unwrap_or_default().to_string_lossy(),
                    path.display()
                )
            })
            .collect()
    }

    fn register_builtin_helper(&mut self) {
        self.handlebars.register_helper("len", Box::new(len));
        self.handlebars
            .register_helper("getlang", Box::new(getlang));
        self.handlebars.register_helper("hash", Box::new(hash));
        self.handlebars
            .register_helper("word_count", Box::new(word_count));
        self.handlebars.register_helper("block", Box::new(block));
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TemplateManager>()?;
    let conf = m.getattr("CONFIG")?.extract::<Config>()?;
    m.add(
        "TEMPLATE_MANAGER",
        TemplateManager::new(
            conf.template_manager.template_dir,
            conf.template_manager.template_suffix,
            conf.template_manager.active_loading,
        ),
    )?;
    Ok(())
}
