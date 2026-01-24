use crate::store::VectorStoreTable;
use error_mapping::AsPyErr;
use lancedb::Connection;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use std::sync::Arc;

use crate::schema::schema_of;

#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone)]
struct VectorStoreService {
    conn: Connection,
}

#[gen_stub_pymethods]
#[pymethods]
impl VectorStoreService {
    #[staticmethod]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.Self]",imports=("typing",))
    )]
    fn connect<'a>(python: Python<'a>, uri: String) -> PyResult<Bound<'a, PyAny>> {
        future_into_py(python, async move {
            let conn = lancedb::connect(uri.as_str())
                .execute()
                .await
                .into_pyresult()?;

            Ok(VectorStoreService { conn })
        })
    }

    fn create_table<'a>(
        &self,
        python: Python<'a>,
        table_name: String,
        ndim: i32,
    ) -> PyResult<Bound<'a, PyAny>> {
        let schema_ref = Arc::new(schema_of(ndim));
        let fut = self.conn
            .create_empty_table(table_name.as_str(), schema_ref.clone())
            .execute();


        future_into_py(python, async move {
            let table = fut
                .await
                .into_pyresult()?;


            Ok(VectorStoreTable::new(table, schema_ref))
        })
    }


    fn open_table<'a>(
        &self,
        python: Python<'a>,
        table_name: String,
    ) -> PyResult<Bound<'a, PyAny>> {
        let fut = self.conn
            .open_table(table_name.as_str())
            .execute();

        future_into_py(python, async move {
            let table = fut
                .await
                .into_pyresult()?;

            let schema_ref = table.schema().await.into_pyresult()?;

            Ok(VectorStoreTable::new(table, schema_ref))
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreService>()?;
    Ok(())
}
