use pyo3::prelude::*;

use axum::Router;
use error_mapping::AsPyErr;
use fabricatio_core::logger::*;
use pyo3_async_runtimes::tokio::future_into_py;
use std::path::PathBuf;
use tower_http::cors::CorsLayer;
use tower_http::services::{ServeDir, ServeFile};

#[pyfunction]
/// Starts the web UI service with the given frontend directory.
fn start_service<'a>(
    py: Python<'a>,
    frontend_dir: PathBuf,
    addr: String,
) -> PyResult<Bound<'a, PyAny>> {
    let static_files =
        ServeDir::new(&frontend_dir).fallback(ServeFile::new(frontend_dir.join("index.html")));

    let app: Router = Router::new()
        .fallback_service(static_files)
        .layer(CorsLayer::permissive());

    info!("Server running on {addr}");

    future_into_py(py, async move {
        let ls = tokio::net::TcpListener::bind(addr).await.into_pyresult()?;
        axum::serve(ls, app.into_make_service())
            .await
            .into_pyresult()?;
        Ok(())
    })
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(start_service, m)?)?;
    Ok(())
}
