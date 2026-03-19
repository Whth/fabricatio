use error_mapping::AsPyErr;
use once_cell::sync::Lazy;
use pyo3::prelude::PyModule;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use thryd::{CompletionRequest, CompletionTag, EmbeddingRequest, EmbeddingTag, Router};

pub static COMPLETION_MODEL_ROUTER: Lazy<Router<CompletionTag>> = Lazy::new(Router::default);

pub static EMBEDDING_MODEL_ROUTER: Lazy<Router<EmbeddingTag>> = Lazy::new(Router::default);

#[pyfunction]
pub fn completion(
    python: Python,

    send_to: String,

    message: String,

    top_p: f32,
    temperature: f32,
) -> PyResult<Bound<PyAny>> {
    let req = CompletionRequest {
        message,
        top_p,
        temperature,
    };

    future_into_py(python, async move {
        COMPLETION_MODEL_ROUTER
            .invoke(send_to, req)
            .await
            .into_pyresult()
    })
}

#[pyfunction]
pub fn embedding(python: Python, send_to: String, texts: Vec<String>) -> PyResult<Bound<PyAny>> {
    let req = EmbeddingRequest { texts };

    future_into_py(python, async move {
        EMBEDDING_MODEL_ROUTER
            .invoke(send_to, req)
            .await
            .into_pyresult()
    })
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(completion, m)?)?;
    m.add_function(wrap_pyfunction!(embedding, m)?)?;

    Ok(())
}
