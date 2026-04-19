use crate::hbs_helpers::*;
use error_mapping::*;
use fabricatio_config::Config;
use fabricatio_constants::*;
use fabricatio_logger::*;
use handlebars::{Handlebars, no_escape};
use path_clean::PathClean;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use pyo3_stub_gen::derive::*;

use pythonize::depythonize;

use rayon::prelude::*;
use serde_json::Value;
use std::path::PathBuf;
use walkdir::WalkDir;

/// Python bindings for the TemplateManager struct.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct TemplateManager {
    #[pyo3(get)]
    templates_stores: Vec<PathBuf>,
    handlebars: Handlebars<'static>,
    suffix: String,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl TemplateManager {
    #[getter]

    /// The count of templates currently registered.
    fn template_count(&self) -> usize {
        self.handlebars.get_templates().len()
    }

    /// Adds a template directory to the list of template directories.
    ///
    /// Args:
    ///     source: The path to the template directory.
    ///     rediscovery: Whether to immediately discover templates (default: False).
    ///
    /// Returns:
    ///     A mutable reference to self for method chaining.
    #[pyo3(signature=(source, rediscovery=false))]
    fn add_store(mut slf: PyRefMut<Self>, source: PathBuf, rediscovery: bool) -> PyRefMut<Self> {
        slf.templates_stores.push(source);

        rediscovery.then(|| slf.discover_templates_inner());
        slf
    }

    /// Adds multiple template directories to the list.
    ///
    /// Args:
    ///     sources: A list of paths to template directories.
    ///     rediscovery: Whether to immediately discover templates (default: False).
    ///
    /// Returns:
    ///     A mutable reference to self for method chaining.
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

    /// Discovers and registers all templates from the configured directories.
    ///
    /// Returns:
    ///     A mutable reference to self for method chaining.
    fn discover_templates(mut slf: PyRefMut<Self>) -> PyRefMut<Self> {
        slf.discover_templates_inner();
        slf
    }

    /// Renders a template with the given data.
    ///
    /// Args:
    ///     name: The path to the template file.
    ///     data: A dictionary or list of dictionaries containing template variables.
    ///
    /// Returns:
    ///     The rendered template string, or a list of strings if data is a list.
    #[gen_stub(skip)]
    fn render_template<'a>(
        &self,
        py: Python<'a>,
        name: PathBuf,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let name = name.clean().to_string_lossy().to_string();

        if data.is_instance_of::<PyList>() {
            trace!("Rendering list of templates: {name}");
            if self.handlebars.get_template(&name).is_none() {
                return Err(PyErr::new::<PyRuntimeError, _>(format!(
                    "Template '{name}' not found"
                )));
            }

            let seq = depythonize::<Vec<Value>>(data).into_pyresult()?;

            let mut rendered_raw: Vec<(usize, String)> = seq
                .iter()
                .enumerate()
                .par_bridge()
                .map(|(idx, item)| {
                    Ok::<(usize, String), PyErr>((
                        idx,
                        self.handlebars.render(&name, item).into_pyresult()?,
                    ))
                })
                .collect::<Vec<_>>()
                .into_iter()
                .try_collect()?;
            rendered_raw.sort_by_key(|x| x.0);
            let rendered: Vec<String> = rendered_raw.into_iter().map(|x| x.1).collect();
            let py_list = PyList::new(py, rendered)?;
            Ok(py_list.as_any().clone())
        } else {
            trace!("Rendering single template: {name}");
            let json_data = depythonize::<Value>(data).into_pyresult()?;

            let rendered_content = self.handlebars.render(&name, &json_data).into_pyresult()?;

            let py_string = PyString::new(py, &rendered_content);
            Ok(py_string.as_any().clone())
        }
    }

    /// Renders a template from a raw template string.
    ///
    /// Args:
    ///     template: The raw template string.
    ///     data: A dictionary or list of dictionaries containing template variables.
    ///
    /// Returns:
    ///     The rendered template string, or a list of strings if data is a list.
    #[gen_stub(skip)]
    fn render_template_raw<'a>(
        &self,
        py: Python<'a>,
        template: &str,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        if data.is_instance_of::<PyList>() {
            let seq = depythonize::<Vec<Value>>(data).into_pyresult()?;

            let mut rendered_raw: Vec<(usize, String)> = seq
                .iter()
                .enumerate()
                .par_bridge()
                .map(|(idx, item)| {
                    Ok::<(usize, String), PyErr>((
                        idx,
                        self.handlebars
                            .render_template(template, item)
                            .into_pyresult()?,
                    ))
                })
                .collect::<Vec<_>>()
                .into_iter()
                .try_collect()?;
            rendered_raw.sort_by_key(|x| x.0);
            let rendered: Vec<String> = rendered_raw.into_iter().map(|x| x.1).collect();
            let py_list = PyList::new(py, &rendered)?;
            Ok(py_list.as_any().clone())
        } else {
            let json_data = depythonize::<Value>(data).into_pyresult()?;

            let rendered_content = self
                .handlebars
                .render_template(template, &json_data)
                .into_pyresult()?;

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

        manager
            .discover_templates_inner()
            .register_builtin_helper()
            .register_partials();
        manager
    }

    /// Discovers and registers all templates from the configured template directories.
    ///
    /// This method clears all previously registered templates and re-scans the template
    /// directories. Templates are processed in reverse order of directories, meaning
    /// that templates found in later directories will override templates with the same
    /// name from earlier directories.
    ///
    /// Note:
    ///     When multiple templates with the same name are found across different directories,
    ///     the template from the directory that appears later in the `templates_dir` vector
    ///     will take precedence and override any previously registered template with the same name.
    ///
    /// Returns:
    ///     A mutable reference to self for method chaining.
    fn discover_templates_inner(&mut self) -> &mut Self {
        self.handlebars.clear_templates();
        self.gather_templates().iter().for_each(|(name, path)| {
            self.handlebars.register_template_file(name, path).unwrap();
        });
        self
    }

    /// Gathers template files from all registered template stores.
    ///
    /// Scans through directories in reverse order to collect template files that match
    /// the configured suffix. For each matching file, generates a tuple containing:
    /// - Template name (derived from file path, without directory prefix and suffix)
    /// - Full path to the template file
    ///
    /// Later directories in the list take precedence over earlier ones when template names conflict.
    fn gather_templates(&self) -> Vec<(String, PathBuf)> {
        self.templates_stores
            .iter()
            .rev()
            .flat_map(|dir| {
                WalkDir::new(dir)
                    .into_iter()
                    .filter_map(core::result::Result::ok)
                    .filter(|e| e.file_type().is_file())
                    .filter(|e| {
                        e.path().extension().and_then(|s| s.to_str()) == Some(self.suffix.as_str())
                    })
                    .map(move |e| {
                        (
                            e.path()
                                .strip_prefix(dir)
                                .unwrap()
                                .clean()
                                .to_string_lossy()
                                .strip_suffix(format!(".{}", self.suffix).as_str())
                                .unwrap()
                                .to_string(),
                            e.path().to_path_buf(),
                        )
                    })
            })
            .inspect(|(name, path)| trace!("Discovered template: {}=>{}", name, path.display()))
            .collect()
    }

    fn register_builtin_helper(&mut self) -> &mut Self {
        self.handlebars.register_helper("len", Box::new(len));
        self.handlebars.register_helper("lang", Box::new(getlang));
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

    fn register_partials(&mut self) -> &mut Self {
        self
    }
}

#[cfg(feature = "stubgen")]
pyo3_stub_gen::inventory::submit! {
    gen_methods_from_python! {
        r#"
        class TemplateManager:
            @overload
            def render_template(self,name:str,data: typing.Dict[str,typing.Any]) -> str: ...
            @overload
            def render_template(self,name:str,data: typing.List[typing.Dict[str,typing.Any]]) -> typing.List[str]: ...

            @overload
            def render_template_raw(self,template: str,data: typing.Dict[str,typing.Any]) -> str: ...
            @overload
            def render_template_raw(self,template: str,data: typing.List[typing.Dict[str,typing.Any]]) -> typing.List[str]: ...

        "#
    }
}

#[cfg(feature = "stubgen")]
pyo3_stub_gen::module_variable!(
    "fabricatio_core.rust",
    TEMPLATE_MANAGER_VARNAME,
    TemplateManager
);

/// Registers the TemplateManager class with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TemplateManager>()?;
    let conf = m.getattr(CONFIG_VARNAME)?.extract::<Config>()?;
    m.add(
        TEMPLATE_MANAGER_VARNAME,
        TemplateManager::new(
            conf.template_manager.template_stores,
            conf.template_manager.template_suffix,
            conf.template_manager.active_loading,
        ),
    )?;
    Ok(())
}
