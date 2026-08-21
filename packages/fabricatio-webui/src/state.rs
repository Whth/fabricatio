use crate::types::*;
use fabricatio_logger::*;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::RwLock;
use std::sync::atomic::{AtomicBool, Ordering};
use tokio::sync::mpsc;

pub struct AppState {
    pub node_registry: RwLock<Vec<NodeTypeDefinition>>,
    /// Package-defined blueprints offered by the board sidebar (baked at startup).
    pub blueprints: RwLock<Vec<BlueprintJson>>,
    pub ws_sessions: RwLock<HashMap<String, mpsc::UnboundedSender<WsMessage>>>,
    pub workflows: RwLock<HashMap<String, BoardJson>>,
    data_dir: PathBuf,
    /// When false, in-memory CRUD still works but save/delete skip writing workflows.json.
    /// Set once at startup; thereafter read-only.
    pub persist_workflows: AtomicBool,
    // Python worker callables (set once at startup; never mutated afterwards)
    pub submit_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    pub cancel_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    pub queue_snapshot_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    pub history_snapshot_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
    /// Re-dispatch roles after a save/delete (no args).
    pub rebuild_roles_fn: std::sync::OnceLock<pyo3::Py<pyo3::PyAny>>,
}

impl AppState {
    pub fn new(data_dir: PathBuf) -> Self {
        let workflows = Self::load_workflows_from_disk(&data_dir);
        Self {
            node_registry: RwLock::new(Vec::new()),
            blueprints: RwLock::new(Vec::new()),
            ws_sessions: RwLock::new(HashMap::new()),
            workflows: RwLock::new(workflows),
            data_dir,
            persist_workflows: AtomicBool::new(true),
            submit_fn: std::sync::OnceLock::new(),
            cancel_fn: std::sync::OnceLock::new(),
            queue_snapshot_fn: std::sync::OnceLock::new(),
            history_snapshot_fn: std::sync::OnceLock::new(),
            rebuild_roles_fn: std::sync::OnceLock::new(),
        }
    }

    pub fn save_workflow(&self, id: String, wf: BoardJson) {
        if let Ok(mut wfs) = self.workflows.write() {
            wfs.insert(id, wf);
            if self.persist_workflows.load(Ordering::Relaxed) {
                Self::persist_to_disk(&self.data_dir, &wfs);
            }
        }
    }

    pub fn get_workflows(&self) -> Vec<(String, BoardJson)> {
        self.workflows
            .read()
            .map(|wfs| wfs.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
            .unwrap_or_default()
    }

    pub fn get_workflow(&self, id: &str) -> Option<BoardJson> {
        self.workflows.read().ok()?.get(id).cloned()
    }

    pub fn delete_workflow(&self, id: &str) -> bool {
        let mut wfs = match self.workflows.write() {
            Ok(g) => g,
            Err(_) => return false,
        };
        if wfs.remove(id).is_some() {
            if self.persist_workflows.load(Ordering::Relaxed) {
                Self::persist_to_disk(&self.data_dir, &wfs);
            }
            true
        } else {
            false
        }
    }

    fn workflows_file(data_dir: &std::path::Path) -> PathBuf {
        data_dir.join("workflows.json")
    }

    fn load_workflows_from_disk(data_dir: &std::path::Path) -> HashMap<String, BoardJson> {
        let path = Self::workflows_file(data_dir);
        match std::fs::read_to_string(&path) {
            Ok(content) => {
                let raw: HashMap<String, serde_json::Value> = serde_json::from_str(&content)
                    .unwrap_or_else(|e| {
                        warn!("Failed to parse {}: {e}", path.display());
                        HashMap::new()
                    });
                raw.into_iter()
                    .map(|(id, value)| {
                        let migrated = BoardJson::migrate_legacy(value);
                        let id_for_log = id.clone();
                        (
                            id,
                            serde_json::from_value(migrated).unwrap_or_else(|e| {
                                warn!("Failed to read board {id_for_log}: {e}");
                                BoardJson {
                                    version: "1.0".into(),
                                    format_version: 2,
                                    name: Some(id_for_log.clone()),
                                    description: None,
                                    roles: vec![],
                                    actions: vec![],
                                    meta: None,
                                }
                            }),
                        )
                    })
                    .collect()
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => HashMap::new(),
            Err(e) => {
                warn!("Failed to read {}: {e}", path.display());
                HashMap::new()
            }
        }
    }

    fn persist_to_disk(data_dir: &std::path::Path, workflows: &HashMap<String, BoardJson>) {
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
