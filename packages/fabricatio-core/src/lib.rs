extern crate core;

mod config;
mod event;
mod hash;
mod hbs_helpers;

mod language;
mod logger;
mod templates;
mod word_split;

use pyo3::prelude::*;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    config::register(python, m)?;
    let conf = m
        .getattr(config::CONFIG_VARNAME)?
        .extract::<config::Config>()?;
    logger::init_logger(conf.debug.log_level.as_str());
    language::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    word_split::register(python, m)?;
    event::register(python, m)?;
    Ok(())
}
