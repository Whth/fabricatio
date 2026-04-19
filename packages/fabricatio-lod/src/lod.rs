use fabricatio_constants::*;
use fabricatio_core::Router;
use pyo3::exceptions::PyImportError;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use thryd::{CompletionRequest, RouteGroupName};

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
    fn with_librian(group: RouteGroupName) -> PyResult<Self> {
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

/// A placeholder function for the lod module.
///
/// This function is currently a no-op placeholder.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn foo() {}

/// Registers the Lod class with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Lod>()?;
    Ok(())
}
