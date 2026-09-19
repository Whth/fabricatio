#![cfg_attr(feature = "stubgen", allow(dead_code, unused))]

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;

mod layout;
mod query;
mod registry;
mod roots;
mod skill;

/// Add every Python-facing type to the module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<skill::Skill>()?;
    m.add_class::<skill::SkillMeta>()?;
    m.add_class::<registry::SkillRegistry>()?;
    Ok(())
}

/// A Python module implemented in Rust.
#[cfg(not(feature = "stubgen"))]
#[pymodule]
fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    fabricatio_logger::init_logger_auto()?;
    register(python, m)?;
    Ok(())
}

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
