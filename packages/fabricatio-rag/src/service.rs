use error_mapping::AsPyErr;
use lancedb::Connection;
use moka::future::FutureExt;
use pyo3::prelude::*;
use pyo3::{Bound, PyResult, Python};
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;

#[gen_stub_pyclass]
#[pyclass]
pub struct LanceDbService {
    conn: Connection,
}

#[gen_stub_pymethods]
#[pymethods]
impl LanceDbService {
    #[staticmethod]
    #[gen_stub(override_return_type(type_repr="typing.Self", imports=("typing")))]
    fn connect<'a>(python: Python<'a>, uri: String) -> PyResult<Bound<'a, PyAny>> {
        future_into_py(
            python,
            async move {
                let conn = lancedb::connect(uri.as_str())
                    .execute()
                    .await
                    .into_pyresult()?;

                Ok(LanceDbService { conn })
            }
            .boxed(),
        )
    }

    fn create_store<'a>(
        &self,
        python: Python<'a>,
        table_name: String,
        columns: Vec<String>,
    ) -> PyResult<Bound<'a, PyAny>> {
        todo!()
    }
    fn get_store<'a>(&self, python: Python<'a>, table_name: String) -> PyResult<Bound<'a, PyAny>> {
        todo!()
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<LanceDbService>()?;

    Ok(())
}
