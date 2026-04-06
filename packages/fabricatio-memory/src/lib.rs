#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

mod constants;
mod memory;
mod service;
mod stat;
mod store;
mod traits;
mod utils;

use crate::constants::*;
use crate::memory::Memory;
use crate::service::MemoryService;
use crate::stat::MemoryStats;
use crate::store::MemoryStore;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::*;
#[cfg(feature = "stubgen")]
module_variable!(
    MODULE_NAME,
    MIN_IMPORTANCE_SCORE_VARNAME,
    u64,
    MIN_IMPORTANCE_SCORE
);
#[cfg(feature = "stubgen")]
module_variable!(
    MODULE_NAME,
    MAX_IMPORTANCE_SCORE_VARNAME,
    u64,
    MAX_IMPORTANCE_SCORE
);

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.

#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(_python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    fabricatio_logger::init_logger_auto()?;
    m.add_class::<Memory>()?;
    m.add_class::<MemoryService>()?;
    m.add_class::<MemoryStore>()?;
    m.add_class::<MemoryStats>()?;

    m.add(MAX_IMPORTANCE_SCORE_VARNAME, MAX_IMPORTANCE_SCORE)?;
    m.add(MIN_IMPORTANCE_SCORE_VARNAME, MIN_IMPORTANCE_SCORE)?;

    Ok(())
}
#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
