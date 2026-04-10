use fabricatio_constants::{CORE_PACKAGE_NAME, ROUTER_VARNAME, RUST_MODULE_NAME};
use fabricatio_core::Router;
use pyo3::exceptions::PyImportError;
use thryd::CompletionRequest;

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct Lod {
    used_group: String,

    router: Router,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl Lod {
    #[staticmethod]
    fn with_librian(group: String) -> PyResult<Self> {
        let router = Python::attach(|py| {
            py.import(CORE_PACKAGE_NAME)?
                .getattr(RUST_MODULE_NAME)?
                .getattr(ROUTER_VARNAME)?
                .extract::<Router>()
                .map_err(|e| PyImportError::new_err(e.to_string()))
        })?;

        Ok(Self {
            used_group: group,
            router,
        })
    }
}

impl Lod {
    async fn completion(&self, req: CompletionRequest) -> thryd::Result<String> {
        self.router
            .completion_router
            .invoke(self.used_group.clone(), req)
            .await
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
