use crate::constants::{ID_FIELD_NAME, TIMESTAMP_FIELD_NAME, VECTOR_FIELD_NAME};
use crate::schema::schema_of;
use crate::store::VectorStoreTable;
use error_mapping::AsPyErr;
use lancedb::Connection;
use lancedb::index::Index;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

/// A service for managing vector stores using LanceDB.
///
/// This service provides methods for connecting to a LanceDB instance,
/// creating tables, opening existing tables, and creating or opening tables.
/// It acts as a high-level interface for vector store operations.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
struct VectorStoreService {
    conn: Connection,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl VectorStoreService {
    /// Connect to a lancedb instance
    #[staticmethod]
    #[cfg_attr(feature = "stubgen", gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.Self]",imports=("typing",))
    ))]
    fn connect<'a>(python: Python<'a>, uri: String) -> PyResult<Bound<'a, PyAny>> {
        future_into_py(python, async move {
            let conn = lancedb::connect(uri.as_str())
                .execute()
                .await
                .into_pyresult()?;

            Ok(VectorStoreService { conn })
        })
    }

    /// Create a table
    fn create_table<'a>(
        &self,
        python: Python<'a>,
        table_name: String,
        ndim: i32,
    ) -> PyResult<Bound<'a, PyAny>> {
        let schema_ref = schema_of(ndim);
        let fut = self
            .conn
            .create_empty_table(table_name.as_str(), schema_ref.clone())
            .execute();

        future_into_py(python, async move {
            let table = fut.await.into_pyresult()?;

            tokio::try_join!(
                table.create_index(&[ID_FIELD_NAME], Index::Auto).execute(),
                table
                    .create_index(&[VECTOR_FIELD_NAME], Index::Auto)
                    .execute(),
                table
                    .create_index(&[TIMESTAMP_FIELD_NAME], Index::Auto)
                    .execute(),
            )
            .into_pyresult()?;

            Ok(VectorStoreTable::new(ndim, table, schema_ref))
        })
    }

    /// Open a table
    fn open_table<'a>(&self, python: Python<'a>, table_name: String) -> PyResult<Bound<'a, PyAny>> {
        let fut = self.conn.open_table(table_name.as_str()).execute();

        future_into_py(python, async move {
            let table = fut.await.into_pyresult()?;

            VectorStoreTable::open(table).await
        })
    }

    /// Create or open a table
    fn create_or_open_table<'a>(
        &self,
        python: Python<'a>,
        table_name: String,
        ndim: i32,
    ) -> PyResult<Bound<'a, PyAny>> {
        let conn = self.conn.clone();

        future_into_py(python, async move {
            if !conn
                .table_names()
                .execute()
                .await
                .into_pyresult()?
                .contains(&table_name)
            {
                let schema_ref = schema_of(ndim);
                let table = conn
                    .create_empty_table(table_name, schema_ref.clone())
                    .execute()
                    .await
                    .into_pyresult()?;
                Ok(VectorStoreTable::new(ndim, table, schema_ref))
            } else {
                let table = conn
                    .open_table(table_name)
                    .execute()
                    .await
                    .into_pyresult()?;
                VectorStoreTable::open(table).await
            }
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<VectorStoreService>()?;
    Ok(())
}
