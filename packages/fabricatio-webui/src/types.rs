use chrono::Utc;
use serde::{Deserialize, Serialize};

// ── Node Registry ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortDefinition {
    pub name: String,
    #[serde(rename = "type")]
    pub port_type: String,
    pub optional: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeTypeDefinition {
    #[serde(rename = "type")]
    pub node_type: String,
    pub title: String,
    pub description: String,
    pub category: String,
    pub input_ports: Vec<PortDefinition>,
    pub output_ports: Vec<PortDefinition>,
    pub capabilities: Vec<String>,
    pub ctx_override: bool,
    pub config_fields: Vec<PortDefinition>,
}

// ── Workflow JSON ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FabricatioNode {
    pub id: String,
    #[serde(rename = "type")]
    pub node_type: String,
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub pos: Option<[f64; 2]>,
    #[serde(default)]
    pub inputs: serde_json::Value,
    #[serde(default)]
    pub config: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FabricatioEdge {
    pub id: String,
    pub source: String,
    pub source_handle: String,
    pub target: String,
    pub target_handle: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowMeta {
    #[serde(default)]
    pub created_at: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    /// base64-encoded PNG thumbnail
    #[serde(default)]
    pub thumbnail: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowJson {
    pub version: String,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub nodes: Vec<FabricatioNode>,
    #[serde(default)]
    pub edges: Vec<FabricatioEdge>,
    #[serde(default)]
    pub init_context: serde_json::Value,
    #[serde(default)]
    pub meta: Option<WorkflowMeta>,
}

// ── Execution ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionRequest {
    pub workflow: WorkflowJson,
    #[serde(default)]
    pub task_input: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionStatus {
    pub execution_id: String,
    pub state: ExecutionState,
    #[serde(default)]
    pub current_node: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionState {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

// ── WebSocket Messages ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum WsMessage {
    ExecutionStart {
        execution_id: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    NodeStart {
        execution_id: String,
        node_id: String,
        node_type: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    NodeDone {
        execution_id: String,
        node_id: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        output: Option<serde_json::Value>,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    NodeError {
        execution_id: String,
        node_id: String,
        error: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        traceback: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    NodeOutput {
        execution_id: String,
        node_id: String,
        output_key: String,
        data: serde_json::Value,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    LlmToken {
        execution_id: String,
        node_id: String,
        token: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    ExecutionDone {
        execution_id: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        result: Option<serde_json::Value>,
        #[serde(skip_serializing_if = "Option::is_none")]
        error: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        timestamp: Option<String>,
    },
    Status {
        queue_length: usize,
        running_count: usize,
    },
}

impl WsMessage {
    /// Inject `timestamp = Some(Utc::now().to_rfc3339())` into every variant
    /// that carries a timestamp field.  Idempotent — keeps an existing timestamp.
    pub fn with_timestamp(mut self) -> Self {
        let now = Utc::now().to_rfc3339();
        match &mut self {
            Self::ExecutionStart { timestamp, .. }
            | Self::NodeStart { timestamp, .. }
            | Self::NodeDone { timestamp, .. }
            | Self::NodeError { timestamp, .. }
            | Self::NodeOutput { timestamp, .. }
            | Self::LlmToken { timestamp, .. }
            | Self::ExecutionDone { timestamp, .. } => {
                if timestamp.is_none() {
                    *timestamp = Some(now);
                }
            }
            Self::Status { .. } => {}
        }
        self
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsSubmit {
    pub workflow: WorkflowJson,
    #[serde(default)]
    pub task_input: Option<serde_json::Value>,
}
