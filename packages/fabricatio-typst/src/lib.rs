mod bib_tools;
pub mod converter;
mod typst_tools;

pub use converter::convert_all_tex_math;
use fabricatio_core::logger::init_logger_auto;
use pyo3::prelude::*;
/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]

fn rust(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_logger_auto()?;
    bib_tools::register(python, m)?;
    typst_tools::register(python, m)?;
    Ok(())
}
