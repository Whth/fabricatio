// src/lib.rs
mod client;
pub mod proto;

use client::EmbeddingClient;
use pyo3::prelude::*;

#[pyclass]
struct PyEmbeddingClient {
    inner: EmbeddingClient,
}

#[pymethods]
impl PyEmbeddingClient {
    #[new]
    fn new(uri: String) -> Self {
        PyEmbeddingClient {
            inner: EmbeddingClient::new(&uri),
        }
    }

    #[pyo3(signature = (inputs, model, truncate=1, normalization="none"))]
    fn embed(
        &self,
        inputs: String,
        model: String,
        truncate: i32,
        normalization: String,
    ) -> PyResult<Vec<f32>> {
        let fut = self.inner.embed(&inputs, &model, truncate, &normalization);
        let rt = tokio::runtime::Runtime::new().map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyException, _>(e.to_string()))?;
        rt.block_on(fut).map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyException, _>(e))
    }
}

#[pymodule]
fn tei_client(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyEmbeddingClient>()?;
    Ok(())
}