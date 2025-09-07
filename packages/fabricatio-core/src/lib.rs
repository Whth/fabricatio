extern crate core;

mod config;
mod event;
mod hash;
mod hbs_helpers;

mod language;
mod templates;
mod word_split;

use fabricatio_config::{CONFIG_VARNAME, Config};
use fabricatio_logger::{LOGGER_VARNAME, Logger};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    config::register(python, m)?;
    let conf: Config = m.getattr(CONFIG_VARNAME)?.extract::<Config>()?;
    let rotation = if let Some(rotation) = conf.debug.rotation {
        rotation.parse().ok()
    } else {
        None
    };
    fabricatio_logger::init_logger(conf.debug.log_level.as_str(), conf.debug.log_dir, rotation)
        .map_err(|e| PyRuntimeError::new_err(e))?;
    m.add(LOGGER_VARNAME, Logger)?;
    language::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    word_split::register(python, m)?;
    event::register(python, m)?;
    Ok(())
}
