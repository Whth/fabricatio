use crate::types::*;
use std::collections::{HashMap, VecDeque};
use std::sync::RwLock;
use tokio::sync::mpsc;

pub struct QueueItem {
    pub execution_id: String,
    pub workflow: WorkflowJson,
    pub task_input: Option<serde_json::Value>,
}

pub struct AppState {
    pub node_registry: RwLock<Vec<NodeTypeDefinition>>,
    pub queue: RwLock<VecDeque<QueueItem>>,
    pub history: RwLock<Vec<ExecutionStatus>>,
    pub active_executions: RwLock<HashMap<String, ExecutionStatus>>,
    pub ws_sessions: RwLock<HashMap<String, mpsc::UnboundedSender<WsMessage>>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            node_registry: RwLock::new(Vec::new()),
            queue: RwLock::new(VecDeque::new()),
            history: RwLock::new(Vec::new()),
            active_executions: RwLock::new(HashMap::new()),
            ws_sessions: RwLock::new(HashMap::new()),
        }
    }

    pub fn register_ws_session(&self, id: String, tx: mpsc::UnboundedSender<WsMessage>) {
        if let Ok(mut sessions) = self.ws_sessions.write() {
            sessions.insert(id, tx);
        }
    }

    pub fn remove_ws_session(&self, id: &str) {
        if let Ok(mut sessions) = self.ws_sessions.write() {
            sessions.remove(id);
        }
    }

    pub fn broadcast(&self, msg: &WsMessage) {
        if let Ok(sessions) = self.ws_sessions.read() {
            for (id, tx) in sessions.iter() {
                if tx.send(msg.clone()).is_err() {
                    fabricatio_logger::warn!("WS session {id} send failed");
                }
            }
        }
    }

    pub fn push_queue(&self, item: QueueItem) {
        if let Ok(mut q) = self.queue.write() {
            q.push_back(item);
        }
    }

    pub fn pop_queue(&self) -> Option<QueueItem> {
        self.queue.write().ok()?.pop_front()
    }

    pub fn queue_snapshot(&self) -> Vec<ExecutionStatus> {
        self.queue
            .read()
            .map(|q| {
                q.iter()
                    .map(|item| ExecutionStatus {
                        execution_id: item.execution_id.clone(),
                        state: ExecutionState::Queued,
                        current_node: None,
                        error: None,
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn history_snapshot(&self) -> Vec<ExecutionStatus> {
        self.history.read().map(|h| h.clone()).unwrap_or_default()
    }

    pub fn active_count(&self) -> usize {
        self.active_executions.read().map(|a| a.len()).unwrap_or(0)
    }

    pub fn queue_len(&self) -> usize {
        self.queue.read().map(|q| q.len()).unwrap_or(0)
    }
}
