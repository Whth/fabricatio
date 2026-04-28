#![feature(iterator_try_collect)]
#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]
extern crate core;

use cfg_if::cfg_if;
use fabricatio_config::Config;
use fabricatio_constants::*;
use fabricatio_logger::{Logger, init_logger};

mod event;
mod formatter;
mod hash;
mod hbs_helpers;
mod language;
mod parser;
mod router;
pub mod router_usage;
mod scan;
pub mod templates;
mod text_file;
mod word_split;

pub use crate::router::Router;
use crate::router::init_router_from_config;
use fabricatio_config::SecretStr;
use pyo3::prelude::*;

cfg_if!(
    if #[cfg(feature = "stubgen")]    {
        use pyo3_stub_gen::{define_stub_info_gatherer, module_variable};
        module_variable!("fabricatio_core.rust", LOGGER_VARNAME, Logger);
        module_variable!("fabricatio_core.rust", CONFIG_VARNAME, Config);
        module_variable!("fabricatio_core.rust", ROUTER_VARNAME, crate::router::Router);
        define_stub_info_gatherer!(stub_info);


    }
);

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SecretStr>()?;
    m.add_class::<Config>()?;
    init_logger(
        fabricatio_config::CONFIG.debug.log_level.as_str(),
        fabricatio_config::CONFIG.debug.log_dir.clone(),
        fabricatio_config::CONFIG
            .debug
            .rotation
            .as_ref()
            .map(|r| r.parse().unwrap_or_default()),
    );

    let r = init_router_from_config()?;
    m.add(ROUTER_VARNAME, r.clone())?;
    m.add(CONFIG_VARNAME, fabricatio_config::CONFIG.clone())?;

    m.add(LOGGER_VARNAME, Logger)?;
    router_usage::register(python, m, r)?;
    language::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    word_split::register(python, m)?;
    event::register(python, m)?;
    scan::register(python, m)?;
    text_file::register(python, m)?;
    router::register(python, m)?;
    parser::register(python, m)?;
    Ok(())
}
