#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

mod constants;
mod memory;
mod service;
mod store;
mod traits;
mod utils;

use crate::memory::Memory;
use crate::service::MemoryService;
use crate::store::MemoryStore;
use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.

#[pymodule]

fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Memory>()?;
    m.add_class::<MemoryService>()?;
    m.add_class::<MemoryStore>()?;

    Ok(())
}

define_stub_info_gatherer!(stub_info);
