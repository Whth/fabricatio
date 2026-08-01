use crate::types::*;
use fabricatio_logger::*;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::RwLock;
use tokio::sync::mpsc;

pub struct AppState {
    pub node_registry: RwLock<Vec<NodeTypeDefinition>>,
    pub ws_sessions: RwLock<HashMap<String, mpsc::UnboundedSender<WsMessage>>>,
    pub workflows: RwLock<HashMap<String, WorkflowJson>>,
    data_dir: PathBuf,
    // Python worker callables (set once at startup; never mutated afterwards)
    pub submit_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    pub cancel_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    pub queue_snapshot_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    pub history_snapshot_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
}

impl AppState {
    pub fn new(data_dir: PathBuf) -> Self {
        let workflows = Self::load_workflows_from_disk(&data_dir);
        Self {
            node_registry: RwLock::new(Vec::new()),
            ws_sessions: RwLock::new(HashMap::new()),
            workflows: RwLock::new(workflows),
            data_dir,
            submit_fn: std::sync::OnceLock::new(),
            cancel_fn: std::sync::OnceLock::new(),
            queue_snapshot_fn: std::sync::OnceLock::new(),
            history_snapshot_fn: std::sync::OnceLock::new(),
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
        let msg = msg.clone().with_timestamp();
        if let Ok(sessions) = self.ws_sessions.read() {
            for (id, tx) in sessions.iter() {
                if tx.send(msg.clone()).is_err() {
                    fabricatio_logger::warn!("WS session {id} send failed");
                }
            }
        }
    }

    // ── Queue (owned by the Python WorkflowWorker) ────────────────────────────
    // Queue/history/active-state live in Python; the Rust side only forwards
    // submissions and snapshots through the callables set in `start_service`.
}

