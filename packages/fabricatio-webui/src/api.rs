use crate::state::{AppState, QueueItem};
use crate::types::*;
use axum::Json;
use axum::extract::State;
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

/// GET /api/workflows — list saved workflows (stub: empty).
pub async fn get_workflows() -> Json<Vec<WorkflowJson>> {
    Json(Vec::new())
}

/// POST /api/workflows — save a workflow (stub: echo back).
pub async fn save_workflow(Json(wf): Json<WorkflowJson>) -> Json<serde_json::Value> {
    let id = wf
        .name
        .clone()
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    Json(serde_json::json!({ "id": id }))
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
