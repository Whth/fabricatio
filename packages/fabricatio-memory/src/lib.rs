#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

mod constants;
mod memory;
mod service;
mod stat;
mod store;
mod traits;
mod utils;

use crate::constants::{
    MAX_IMPORTANCE_SCORE, MAX_IMPORTANCE_SCORE_VARNAME, MIN_IMPORTANCE_SCORE,
    MIN_IMPORTANCE_SCORE_VARNAME, MODULE_NAME,
};
use crate::memory::Memory;
use crate::service::MemoryService;
use crate::stat::MemoryStats;
use crate::store::MemoryStore;
use fabricatio_logger::init_logger_auto;
use pyo3::prelude::*;
use pyo3_stub_gen::{define_stub_info_gatherer, module_variable};

module_variable!(MODULE_NAME, MIN_IMPORTANCE_SCORE_VARNAME, f64);
module_variable!(MODULE_NAME, MAX_IMPORTANCE_SCORE_VARNAME, f64);

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.

// #[cfg(not(feature = "stubgen"))]
#[pymodule]

fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    m.add_class::<Memory>()?;
    m.add_class::<MemoryService>()?;
    m.add_class::<MemoryStore>()?;
    m.add_class::<MemoryStats>()?;

    m.add(MAX_IMPORTANCE_SCORE_VARNAME, MAX_IMPORTANCE_SCORE)?;
    m.add(MIN_IMPORTANCE_SCORE_VARNAME, MIN_IMPORTANCE_SCORE)?;

    Ok(())
}

define_stub_info_gatherer!(stub_info);
