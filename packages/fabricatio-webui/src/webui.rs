use crate::api;
use crate::state::AppState;
use crate::types::{BlueprintJson, NodeTypeDefinition, WsMessage};
use crate::ws;
use axum::Router;
use axum::routing::{get, post};
use error_mapping::AsPyErr;
use fabricatio_logger::*;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use std::path::PathBuf;
use std::sync::{Arc, OnceLock};
use tower_http::cors::{AllowOrigin, CorsLayer};
use tower_http::services::{ServeDir, ServeFile};

use pyo3_stub_gen::derive::*;

/// Global handle to the running service state, used by `rust_broadcast` to
/// push Python-side events out to every connected WS session.
static STATE: OnceLock<Arc<AppState>> = OnceLock::new();

fn create_router(
    state: Arc<AppState>,
    frontend_dir: PathBuf,
    allowed_origins: Vec<String>,
) -> Router {
    let static_files =
        ServeDir::new(&frontend_dir).fallback(ServeFile::new(frontend_dir.join("index.html")));

    let cors = if allowed_origins.is_empty() {
        CorsLayer::permissive()
    } else {
        CorsLayer::new().allow_origin(AllowOrigin::list(
            allowed_origins.iter().filter_map(|o| o.parse().ok()),
        ))
    };

    Router::new()
        .route("/api/nodes", get(api::get_nodes))
        .route("/api/blueprints", get(api::get_blueprints))
        .route(
            "/api/workflows",
            get(api::get_workflows).post(api::save_workflow),
        )
        .route(
            "/api/workflows/{id}",
            get(api::get_workflow).delete(api::delete_workflow),
        )
        .route("/api/execute", post(api::submit_execution))
        .route("/api/interrupt", post(api::interrupt_execution))
        .route("/api/queue", get(api::get_queue))
        .route("/api/history", get(api::get_history))
        .route("/ws", get(ws::ws_handler))
        .fallback_service(static_files)
        .layer(cors)
        .with_state(state)
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pyfunction]
/// Broadcast a serialized WsMessage to every connected WS session.
pub(crate) fn rust_broadcast(payload_json: String) {
    let Some(state) = STATE.get() else { return };
    let Ok(msg) = serde_json::from_str::<WsMessage>(&payload_json) else {
        return;
    };
    state.broadcast(&msg);
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[gen_stub(
    override_return_type(type_repr = "typing.Awaitable[None]", imports = ("typing",))
)]
#[pyfunction]
/// Starts the web UI service with the given frontend and data directories.
///
/// The four ``*_fn`` callables are the Python WorkflowWorker entry points:
/// submit(execution_id, workflow_json, task_input_json), cancel() -> bool,
/// queue_snapshot() -> str, history_snapshot() -> str.
fn start_service<'a>(
    py: Python<'a>,
    frontend_dir: PathBuf,
    data_dir: PathBuf,
    addr: String,
    node_registry_json: String,
    blueprints_json: String,
    allowed_origins: Vec<String>,
    submit_fn: Bound<'a, PyAny>,
    cancel_fn: Bound<'a, PyAny>,
    queue_snapshot_fn: Bound<'a, PyAny>,
    history_snapshot_fn: Bound<'a, PyAny>,
    rebuild_roles_fn: Bound<'a, PyAny>,
) -> PyResult<Bound<'a, PyAny>> {
    let registry: Vec<NodeTypeDefinition> = serde_json::from_str(&node_registry_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let blueprints: Vec<BlueprintJson> = serde_json::from_str(&blueprints_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let state = Arc::new(AppState::new(data_dir));
    if let Ok(mut reg) = state.node_registry.write() {
        *reg = registry;
    }
    if let Ok(mut bp) = state.blueprints.write() {
        *bp = blueprints;
    }

    let _ = STATE.set(Arc::clone(&state));
    let _ = state.submit_fn.set(submit_fn.unbind());
    let _ = state.cancel_fn.set(cancel_fn.unbind());
    let _ = state.queue_snapshot_fn.set(queue_snapshot_fn.unbind());
    let _ = state.history_snapshot_fn.set(history_snapshot_fn.unbind());
    let _ = state.rebuild_roles_fn.set(rebuild_roles_fn.unbind());

    let app = create_router(state, frontend_dir, allowed_origins);
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
    m.add_function(wrap_pyfunction!(rust_broadcast, m)?)?;
    Ok(())
}
