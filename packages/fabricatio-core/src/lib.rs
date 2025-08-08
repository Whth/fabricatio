extern crate core;

mod config;
mod event;
mod hash;
mod hbs_helpers;

mod language;
mod templates;
mod word_split;

use crate::config::CONFIG_VARNAME;
use fabricatio_constants::NAME;
use pyo3::exceptions::PyModuleNotFoundError;
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
    fabricatio_logger::init_logger(conf.debug.log_level.as_str());
    language::register(python, m)?;
    templates::register(python, m)?;
    hash::register(python, m)?;
    word_split::register(python, m)?;
    event::register(python, m)?;
    Ok(())
}




pub fn init_logger_auto() -> PyResult<()>{
    let level=Python::with_gil(
        |py|{

            let mut n = NAME.to_string();
            n.push_str("core");
            if let Ok(m)= py.import(n) &&
                let Ok(conf_obj)=m.getattr(CONFIG_VARNAME)&&
                let Ok(conf) = conf_obj.extract::<config::Config>(){
                Ok(conf.debug.log_level)
            }else {
                Err(PyModuleNotFoundError::new_err("Config module not found"))
            }


        }
    )?;
    fabricatio_logger::init_logger(level.as_str());
    Ok(())
}

