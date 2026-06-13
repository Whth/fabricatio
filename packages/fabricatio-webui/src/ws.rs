use crate::state::{AppState, QueueItem};
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

    // Reader task: parse incoming WsSubmit messages
    let state_clone = Arc::clone(&state);
    let sid = session_id.clone();
    let mut recv_task = tokio::spawn(async move {
        while let Some(Ok(msg)) = receiver.next().await {
            match msg {
                Message::Text(text) => {
                    if let Ok(submit) = serde_json::from_str::<WsSubmit>(&text) {
                        let execution_id = Uuid::new_v4().to_string();
                        let item = QueueItem {
                            execution_id: execution_id.clone(),
                            workflow: submit.workflow,
                            task_input: submit.task_input,
                        };
                        state_clone.push_queue(item);
                        state_clone.broadcast(&WsMessage::Status {
                            queue_length: state_clone.queue_len(),
                            running_count: state_clone.active_count(),
                        });
                        fabricatio_logger::info!("WS {sid} queued execution {execution_id}");
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
