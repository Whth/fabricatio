use crate::state::AppState;
use crate::types::*;
use axum::extract::ws::{Message, WebSocket};
use axum::extract::{State, WebSocketUpgrade};
use axum::response::IntoResponse;
use futures::{SinkExt, StreamExt};
use std::sync::Arc;
use uuid::Uuid;

pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(socket: WebSocket, state: Arc<AppState>) {
    let (mut sender, mut receiver) = socket.split();
    let session_id = Uuid::new_v4().to_string();
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<WsMessage>();

    state.register_ws_session(session_id.clone(), tx);
    fabricatio_logger::info!("WS session {session_id} connected");

    // Writer task: forward from channel to websocket
    let mut send_task = tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            if let Ok(text) = serde_json::to_string(&msg) {
                if sender.send(Message::Text(text.into())).await.is_err() {
                    break;
                }
            }
        }
    });

    // Reader task: parse incoming WsSubmit messages and forward to the Python worker
    let state_clone = Arc::clone(&state);
    let sid = session_id.clone();
    let mut recv_task = tokio::spawn(async move {
        while let Some(Ok(msg)) = receiver.next().await {
            match msg {
                Message::Text(text) => {
                    if let Ok(submit) = serde_json::from_str::<WsSubmit>(&text) {
                        let execution_id = Uuid::new_v4().to_string();
                        let wf_json = match serde_json::to_string(&submit.workflow) {
                            Ok(s) => s,
                            Err(e) => {
                                fabricatio_logger::warn!("WS {sid}: cannot serialize workflow: {e}");
                                continue;
                            }
                        };
                        let task_json = submit
                            .task_input
                            .map(|v| v.to_string())
                            .unwrap_or_else(|| "null".to_string());
                        if let Some(submit_fn) = state_clone.submit_fn.get() {
                            let res = pyo3::Python::attach(|py| {
                                submit_fn.call1(py, (execution_id.clone(), wf_json, task_json))
                            });
                            if let Err(e) = res {
                                fabricatio_logger::warn!("WS {sid}: submit rejected: {e}");
                            } else {
                                fabricatio_logger::info!("WS {sid} queued execution {execution_id}");
                            }
                        }
                    }
                }
                Message::Close(_) => break,
                _ => {}
            }
        }
    });

    // Wait for either task to finish
    tokio::select! {
        _ = &mut send_task => recv_task.abort(),
        _ = &mut recv_task => send_task.abort(),
    }

    state.remove_ws_session(&session_id);
    fabricatio_logger::info!("WS session {session_id} disconnected");
}
