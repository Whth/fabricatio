use crate::config::Config;
use crate::hbs_helpers::*;
use handlebars::{Handlebars, no_escape};
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
    #[pyo3(get)]
    templates_stores: Vec<PathBuf>,
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

    /// Add a template directory to the list of template directories.
    #[pyo3(signature=(source, rediscovery=false))]
    fn add_store(mut slf: PyRefMut<Self>, source: PathBuf, rediscovery: bool) -> PyRefMut<Self> {
        slf.templates_stores.push(source);

        rediscovery.then(|| slf.discover_templates_inner());
        slf
    }
    #[pyo3(signature=(sources, rediscovery=false))]
    fn add_stores(
        mut slf: PyRefMut<Self>,
        sources: Vec<PathBuf>,
        rediscovery: bool,
    ) -> PyRefMut<Self> {
        slf.templates_stores.extend(sources);
        rediscovery.then(|| slf.discover_templates_inner());
        slf
    }

    /// Discover the templates in the template directories.
    fn discover_templates(mut slf: PyRefMut<Self>) -> PyRefMut<Self> {
        slf.discover_templates_inner();
        slf
    }

    /// Get the source code of a template.
    fn get_template_source(&self, name: &str) -> Option<String> {
        self.gather_templates()
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
            if self.handlebars.get_template(name).is_none() {
                return Err(PyErr::new::<PyRuntimeError, _>(format!(
                    "Template {name} not found"
                )));
            }

            let seq = depythonize::<Vec<Value>>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))?;

            let mut rendered_raw: Vec<(usize, String)> = seq
                .iter()
                .enumerate()
                .par_bridge()
                .map(|(idx, item)| {
                    (
                        idx,
                        self.handlebars
                            .render(name, item)
                            .expect(&format!("Rendering error for {name} when rendering {item}")),
                    )
                })
                .collect();
            rendered_raw.sort_by_key(|x| x.0);
            let rendered: Vec<String> = rendered_raw.into_iter().map(|x| x.1).collect();
            let py_list = PyList::new(py, rendered).expect("Failed to create PyList");
            Ok(py_list.as_any().clone())
        } else {
            debug!("Rendering single template");
            let json_data = depythonize::<Value>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))?;

            let rendered_content = self.handlebars.render(name, &json_data).map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!(
                    "Rendering error {e} for {name} when rendering {json_data}"
                ))
            })?;

            let py_string = PyString::new(py, &rendered_content);
            Ok(py_string.as_any().clone())
        }
    }

    fn render_template_raw<'a>(
        &self,
        py: Python<'a>,
        template: &str,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        if data.is_instance_of::<PyList>() {
            let seq = depythonize::<Vec<Value>>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))?;

            let mut rendered_raw: Vec<(usize, String)> = seq
                .iter()
                .enumerate()
                .par_bridge()
                .map(|(idx, item)| {
                    (
                        idx,
                        self.handlebars
                            .render_template(template, item)
                            .expect(&format!(
                                "Rendering error for {template} when rendering {item}"
                            )),
                    )
                })
                .collect();
            rendered_raw.sort_by_key(|x| x.0);
            let rendered: Vec<String> = rendered_raw.into_iter().map(|x| x.1).collect();
            let py_list = PyList::new(py, &rendered).expect("Failed to create PyList");
            Ok(py_list.as_any().clone())
        } else {
            let json_data = depythonize::<Value>(data)
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))?;

            let rendered_content = self
                .handlebars
                .render_template(template, &json_data)
                .unwrap_or_else(|_| {
                    panic!("Rendering error for {template} when rendering {json_data}")
                });

            let py_string = PyString::new(py, &rendered_content);
            Ok(py_string.as_any().clone())
        }
    }
}

impl TemplateManager {
    fn new(template_dir: Vec<PathBuf>, suffix: String, active_loading: bool) -> Self {
        // Convert Python paths to Rust PathBufs

        let mut handlebars = Handlebars::new();
        handlebars.set_dev_mode(active_loading);
        handlebars.register_escape_fn(no_escape);

        let mut manager = Self {
            templates_stores: template_dir,
            handlebars,
            suffix,
        };

        manager.discover_templates_inner().register_builtin_helper();
        manager
    }

    /// Discovers and registers all templates from the configured template directories.
    ///
    /// This method clears all previously registered templates and re-scans the template
    /// directories. Templates are processed in reverse order of directories, meaning
    /// that templates found in later directories will override templates with the same
    /// name from earlier directories.
    ///
    /// # Template Override Behavior
    ///
    /// When multiple templates with the same name are found across different directories,
    /// the template from the directory that appears later in the `templates_dir` vector
    /// will take precedence and override any previously registered template with the same name.
    ///
    /// # Returns
    ///
    /// Returns a mutable reference to self for method chaining.
    fn discover_templates_inner(&mut self) -> &mut Self {
        self.handlebars.clear_templates();
        self.gather_templates().iter().for_each(|path| {
            let name = path.file_stem().unwrap().to_str().unwrap();
            self.handlebars.register_template_file(name, path).unwrap();
        });
        self
    }

    /// Returns a list of all discovered templates.
    fn gather_templates(&self) -> Vec<PathBuf> {
        self.templates_stores
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

    fn register_builtin_helper(&mut self) -> &mut Self {
        self.handlebars.register_helper("len", Box::new(len));
        self.handlebars
            .register_helper("lang", Box::new(getlang));
        self.handlebars.register_helper("hash", Box::new(hash));
        self.handlebars
            .register_helper("words", Box::new(word_count));
        self.handlebars.register_helper("block", Box::new(block));
        self.handlebars
            .register_helper("ls", Box::new(list_out_string));
        self.handlebars.register_helper("code", Box::new(code));

        self.handlebars
            .register_helper("date", Box::new(timestamp_to_date));
        self.handlebars.register_helper("head", Box::new(head));
        self.handlebars.register_helper("join", Box::new(join));
        self
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TemplateManager>()?;
    let conf = m.getattr("CONFIG")?.extract::<Config>()?;
    m.add(
        "TEMPLATE_MANAGER",
        TemplateManager::new(
            conf.template_manager.template_stores,
            conf.template_manager.template_suffix,
            conf.template_manager.active_loading,
        ),
    )?;
    Ok(())
}
