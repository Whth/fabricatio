use crate::api;
use crate::state::AppState;
use crate::types::NodeTypeDefinition;
use crate::ws;
use axum::Router;
use axum::routing::{get, post};
use error_mapping::AsPyErr;
use fabricatio_logger::*;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use std::path::PathBuf;
use std::sync::Arc;
use tower_http::cors::CorsLayer;
use tower_http::services::{ServeDir, ServeFile};

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

fn create_router(state: Arc<AppState>, frontend_dir: PathBuf) -> Router {
    let static_files =
        ServeDir::new(&frontend_dir).fallback(ServeFile::new(frontend_dir.join("index.html")));

    Router::new()
        .route("/api/nodes", get(api::get_nodes))
        .route(
            "/api/workflows",
            get(api::get_workflows).post(api::save_workflow),
        )
        .route("/api/execute", post(api::submit_execution))
        .route("/api/interrupt", post(api::interrupt_execution))
        .route("/api/queue", get(api::get_queue))
        .route("/api/history", get(api::get_history))
        .route("/ws", get(ws::ws_handler))
        .fallback_service(static_files)
        .layer(CorsLayer::permissive())
        .with_state(state)
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Starts the web UI service with the given frontend directory.
fn start_service<'a>(
    py: Python<'a>,
    frontend_dir: PathBuf,
    addr: String,
    node_registry_json: String,
) -> PyResult<Bound<'a, PyAny>> {
    let registry: Vec<NodeTypeDefinition> = serde_json::from_str(&node_registry_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let state = Arc::new(AppState::new());
    if let Ok(mut reg) = state.node_registry.write() {
        *reg = registry;
    }

    let app = create_router(state, frontend_dir);
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
