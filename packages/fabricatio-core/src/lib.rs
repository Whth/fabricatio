extern crate core;

mod config;
mod event;
mod hash;
mod hbs_helpers;

mod language;
mod templates;
mod word_split;

use fabricatio_config::{CONFIG_VARNAME, Config};
use pyo3::prelude::*;
use fabricatio_logger::{LOGGER_VARNAME,Logger};

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    config::register(python, m)?;
    let conf = m.getattr(CONFIG_VARNAME)?.extract::<Config>()?;
    fabricatio_logger::init_logger(conf.debug.log_level.as_str());
    m.add(LOGGER_VARNAME,Logger)?;
    language::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    word_split::register(python, m)?;
    event::register(python, m)?;
    Ok(())
}
