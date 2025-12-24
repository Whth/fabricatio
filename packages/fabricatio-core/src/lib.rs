#![cfg_attr(
    any(feature = "stubgen", not(feature = "pymodule")),
    allow(dead_code, unused,)
)]

use cfg_if::cfg_if;
pub mod config;
pub mod constants;
mod event;
mod hash;
mod hbs_helpers;
mod language;
pub mod logger;
mod scan;
mod templates;
mod text_file;
mod word_split;

use crate::config::{CONFIG_VARNAME, Config};
use crate::logger::{LOGGER_VARNAME, Logger};

cfg_if!(
    if #[cfg(feature = "stubgen")]    {
        use pyo3_stub_gen::{define_stub_info_gatherer, module_variable};
        module_variable!("fabricatio_core.rust", LOGGER_VARNAME, Logger);
        module_variable!("fabricatio_core.rust", CONFIG_VARNAME, Config);
        define_stub_info_gatherer!(stub_info);

    }else if #[cfg(feature = "pymodule")] {

        use crate::config::SecretStr;
        use pyo3::exceptions::PyRuntimeError;
        use pyo3::prelude::*;
    }

);

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(all(not(feature = "stubgen"), feature = "pymodule"))]
#[pymodule]
#[pyo3(name = "rust")]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SecretStr>()?;
    m.add_class::<Config>()?;
    m.add(CONFIG_VARNAME, Config::new()?)?;
    let conf: Config = m.getattr(CONFIG_VARNAME)?.extract::<Config>()?;
    let rotation = if let Some(rotation) = conf.debug.rotation {
        rotation.parse().ok()
    } else {
        None
    };
    logger::init_logger(conf.debug.log_level.as_str(), conf.debug.log_dir, rotation)
        .map_err(PyRuntimeError::new_err)?;
    m.add(LOGGER_VARNAME, Logger)?;

    language::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    word_split::register(python, m)?;
    event::register(python, m)?;
    scan::register(python, m)?;
    text_file::register(python, m)?;

    Ok(())
}
