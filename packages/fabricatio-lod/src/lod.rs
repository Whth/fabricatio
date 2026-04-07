use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct Lod {
    used_group: String,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl Lod {
    #[new]
    fn new(group: String) -> PyResult<Self> {
        todo!()
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn foo() {}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(foo, m)?)?;
    m.add_class::<Lod>()?;
    Ok(())
}
