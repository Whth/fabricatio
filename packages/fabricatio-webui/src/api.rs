use crate::state::{AppState, QueueItem};
use crate::types::*;
use axum::Json;
use axum::extract::{Path, State};
use std::sync::Arc;
use uuid::Uuid;

/// GET /api/nodes — return all registered node type definitions.
pub async fn get_nodes(State(state): State<Arc<AppState>>) -> Json<Vec<NodeTypeDefinition>> {
    let registry = state
        .node_registry
        .read()
        .map(|r| r.clone())
        .unwrap_or_default();
    Json(registry)
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

/// GET /api/workflows/:id — get a single saved workflow.
pub async fn get_workflow(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<WorkflowJson>, (axum::http::StatusCode, String)> {
    state.get_workflow(&id).map(Json).ok_or_else(|| {
        (
            axum::http::StatusCode::NOT_FOUND,
            format!("workflow '{id}' not found"),
        )
    })
}

/// POST /api/workflows — save a workflow.
pub async fn save_workflow(
    State(state): State<Arc<AppState>>,
    Json(mut wf): Json<WorkflowJson>,
) -> Json<serde_json::Value> {
    let id = wf
        .name
        .clone()
        .filter(|n| !n.is_empty())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    // Inject timestamps: preserve created_at if workflow already exists
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
    Json(serde_json::json!({ "id": id }))
}

/// DELETE /api/workflows/:id — delete a saved workflow.
pub async fn delete_workflow(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, (axum::http::StatusCode, String)> {
    if state.delete_workflow(&id) {
        Ok(Json(serde_json::json!({ "ok": true })))
    } else {
        Err((
            axum::http::StatusCode::NOT_FOUND,
            format!("workflow '{id}' not found"),
        ))
    }
}

/// POST /api/execute — submit a workflow for execution.
pub async fn submit_execution(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ExecutionRequest>,
) -> Json<serde_json::Value> {
    let execution_id = Uuid::new_v4().to_string();

    let item = QueueItem {
        execution_id: execution_id.clone(),
        workflow: req.workflow,
        task_input: req.task_input,
    };

    state.push_queue(item);

    // Broadcast updated status
    state.broadcast(&WsMessage::Status {
        queue_length: state.queue_len(),
        running_count: state.active_count(),
    });

    Json(serde_json::json!({ "execution_id": execution_id }))
}

/// POST /api/interrupt — cancel running execution (stub).
pub async fn interrupt_execution() -> Json<serde_json::Value> {
    Json(serde_json::json!({ "ok": true, "message": "interrupt not yet implemented" }))
}

/// GET /api/queue — current queue status.
pub async fn get_queue(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    let queue = state.queue_snapshot();
    let active = state
        .active_executions
        .read()
        .map(|a| a.values().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    Json(serde_json::json!({
        "queue": queue,
        "active": active,
    }))
}

/// GET /api/history — execution history.
pub async fn get_history(State(state): State<Arc<AppState>>) -> Json<Vec<ExecutionStatus>> {
    Json(state.history_snapshot())
}
