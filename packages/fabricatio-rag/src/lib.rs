#![feature(iterator_try_collect)]
#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

pub mod constants;
pub mod schema;
mod service;
mod store;
mod tei;
mod tei_client;
mod utils;

use fabricatio_logger::init_logger_auto;
use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    tei_client::register(python, m)?;
    service::register(python, m)?;
    store::register(python, m)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
