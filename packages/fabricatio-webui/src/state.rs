use crate::types::*;
use fabricatio_logger::*;
use std::collections::{HashMap, VecDeque};
use std::path::PathBuf;
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
    pub workflows: RwLock<HashMap<String, WorkflowJson>>,
    data_dir: PathBuf,
}

impl AppState {
    pub fn new(data_dir: PathBuf) -> Self {
        let workflows = Self::load_workflows_from_disk(&data_dir);
        Self {
            node_registry: RwLock::new(Vec::new()),
            queue: RwLock::new(VecDeque::new()),
            history: RwLock::new(Vec::new()),
            active_executions: RwLock::new(HashMap::new()),
            ws_sessions: RwLock::new(HashMap::new()),
            workflows: RwLock::new(workflows),
            data_dir,
        }
    }

    // ── Workflow CRUD ──────────────────────────────────────────────────────────

    pub fn save_workflow(&self, id: String, wf: WorkflowJson) {
        if let Ok(mut wfs) = self.workflows.write() {
            wfs.insert(id, wf);
            Self::persist_to_disk(&self.data_dir, &wfs);
        }
    }

    pub fn get_workflows(&self) -> Vec<(String, WorkflowJson)> {
        self.workflows
            .read()
            .map(|wfs| wfs.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
            .unwrap_or_default()
    }

    pub fn get_workflow(&self, id: &str) -> Option<WorkflowJson> {
        self.workflows.read().ok()?.get(id).cloned()
    }

    pub fn delete_workflow(&self, id: &str) -> bool {
        let mut wfs = match self.workflows.write() {
            Ok(g) => g,
            Err(_) => return false,
        };
        if wfs.remove(id).is_some() {
            Self::persist_to_disk(&self.data_dir, &wfs);
            true
        } else {
            false
        }
    }

    // ── Disk Persistence ──────────────────────────────────────────────────────

    fn workflows_file(data_dir: &std::path::Path) -> PathBuf {
        data_dir.join("workflows.json")
    }

    fn load_workflows_from_disk(data_dir: &std::path::Path) -> HashMap<String, WorkflowJson> {
        let path = Self::workflows_file(data_dir);
        match std::fs::read_to_string(&path) {
            Ok(content) => serde_json::from_str(&content).unwrap_or_else(|e| {
                warn!("Failed to parse {}: {e}", path.display());
                HashMap::new()
            }),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => HashMap::new(),
            Err(e) => {
                warn!("Failed to read {}: {e}", path.display());
                HashMap::new()
            }
        }
    }

    fn persist_to_disk(data_dir: &std::path::Path, workflows: &HashMap<String, WorkflowJson>) {
        let path = Self::workflows_file(data_dir);
        if let Err(e) = std::fs::create_dir_all(data_dir) {
            warn!("Failed to create {}: {e}", data_dir.display());
            return;
        }
        let tmp = path.with_extension("json.tmp");
        match serde_json::to_string_pretty(workflows) {
            Ok(json) => {
                if let Err(e) = std::fs::write(&tmp, &json) {
                    warn!("Failed to write {}: {e}", tmp.display());
                    return;
                }
                if let Err(e) = std::fs::rename(&tmp, &path) {
                    warn!(
                        "Failed to rename {} -> {}: {e}",
                        tmp.display(),
                        path.display()
                    );
                }
            }
            Err(e) => warn!("Failed to serialize workflows: {e}"),
        }
    }

    // ── WebSocket ──────────────────────────────────────────────────────────────

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

    // ── Queue ──────────────────────────────────────────────────────────────────

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
