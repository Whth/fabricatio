use crate::state::AppState;
use crate::types::*;
use axum::Json;
use axum::extract::{Path, State};
use std::sync::Arc;
use uuid::Uuid;

/// Call a Python worker snapshot callable that returns a JSON string.
/// Both snapshot callables (queue_snapshot, history_snapshot) take no args.
fn call_json(f: &std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>) -> Option<serde_json::Value> {
    let f = f.get()?;
    pyo3::Python::attach(|py| {
        let r = f.call0(py).ok()?;
        let s: String = r.extract(py).ok()?;
        serde_json::from_str(&s).ok()
    })
}

/// GET /api/nodes — return all registered node type definitions.
pub async fn get_nodes(State(state): State<Arc<AppState>>) -> Json<Vec<NodeTypeDefinition>> {
    let registry = state
        .node_registry
        .read()
        .map(|r| r.clone())
        .unwrap_or_default();
    Json(registry)
}

/// GET /api/blueprints — return the package-defined blueprint catalog.
pub async fn get_blueprints(State(state): State<Arc<AppState>>) -> Json<Vec<BlueprintJson>> {
    let blueprints = state
        .blueprints
        .read()
        .map(|b| b.clone())
        .unwrap_or_default();
    Json(blueprints)
}

/// GET /api/workflows — list saved workflows (with id).
pub async fn get_workflows(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let wfs = state.get_workflows();
    let list: Vec<serde_json::Value> = wfs
        .into_iter()
        .map(|(id, wf)| {
            let mut val = serde_json::to_value(&wf).unwrap_or_default();
            if let Some(obj) = val.as_object_mut() {
                obj.insert("id".to_string(), serde_json::Value::String(id));
            }
            val
        })
        .collect();
    Json(serde_json::Value::Array(list))
}

/// GET /api/workflows/:id — get a single saved board.
pub async fn get_workflow(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<BoardJson>, (axum::http::StatusCode, String)> {
    state.get_workflow(&id).map(Json).ok_or_else(|| {
        (
            axum::http::StatusCode::NOT_FOUND,
            format!("board '{id}' not found"),
        )
    })
}

/// POST /api/workflows — save a board, then re-dispatch roles.
pub async fn save_workflow(
    State(state): State<Arc<AppState>>,
    Json(mut wf): Json<BoardJson>,
) -> Json<serde_json::Value> {
    let id = wf
        .name
        .clone()
        .filter(|n| !n.is_empty())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    // Inject timestamps: preserve created_at if the board already exists
    let now = chrono::Utc::now().to_rfc3339();
    let created_at = state
        .get_workflow(&id)
        .and_then(|existing| existing.meta)
        .and_then(|m| m.created_at)
        .unwrap_or_else(|| now.clone());

    let tags = wf.meta.as_ref().map(|m| m.tags.clone()).unwrap_or_default();
    let thumbnail = wf.meta.as_ref().and_then(|m| m.thumbnail.clone());

    wf.meta = Some(WorkflowMeta {
        created_at: Some(created_at),
        updated_at: Some(now),
        tags,
        thumbnail,
    });

    state.save_workflow(id.clone(), wf);
    rebuild_roles(&state);
    Json(serde_json::json!({ "id": id }))
}

/// DELETE /api/workflows/:id — delete a saved board, then re-dispatch roles.
pub async fn delete_workflow(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, (axum::http::StatusCode, String)> {
    if state.delete_workflow(&id) {
        rebuild_roles(&state);
        Ok(Json(serde_json::json!({ "ok": true })))
    } else {
        Err((
            axum::http::StatusCode::NOT_FOUND,
            format!("board '{id}' not found"),
        ))
    }
}

/// Ask the Python worker to re-dispatch roles from the persisted store.
fn rebuild_roles(state: &Arc<AppState>) {
    let Some(rebuild) = state.rebuild_roles_fn.get() else {
        return;
    };
    let _ = pyo3::Python::attach(|py| rebuild.call0(py));
}

/// POST /api/execute — publish a task; dispatched roles serve it by namespace.
pub async fn submit_execution(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ExecutionRequest>,
) -> Result<Json<serde_json::Value>, (axum::http::StatusCode, String)> {
    let execution_id = Uuid::new_v4().to_string();
    let task_json = serde_json::to_string(&req.task)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let submit = state.submit_fn.get().ok_or_else(|| {
        (
            axum::http::StatusCode::SERVICE_UNAVAILABLE,
            "worker not ready".into(),
        )
    })?;
    let res = pyo3::Python::attach(|py| submit.call1(py, (execution_id.clone(), task_json)));
    if let Err(e) = res {
        return Err((
            axum::http::StatusCode::SERVICE_UNAVAILABLE,
            format!("worker rejected submission: {e}"),
        ));
    }
    Ok(Json(serde_json::json!({ "execution_id": execution_id })))
}

/// POST /api/interrupt — cancel the running execution.
pub async fn interrupt_execution(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let ok = pyo3::Python::attach(|py| {
        state
            .cancel_fn
            .get()
            .and_then(|f| f.call1(py, ()).ok())
            .and_then(|r| r.extract::<bool>(py).ok())
            .unwrap_or(false)
    });
    Json(serde_json::json!({ "ok": ok }))
}

/// GET /api/queue — current queue status (owned by the Python worker).
pub async fn get_queue(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let snap = call_json(&state.queue_snapshot_fn)
        .unwrap_or_else(|| serde_json::json!({ "queue": [], "active": [] }));
    Json(snap)
}

/// GET /api/history — execution history (owned by the Python worker).
pub async fn get_history(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let snap = call_json(&state.history_snapshot_fn).unwrap_or_else(|| serde_json::json!([]));
    Json(snap)
}
