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
    },
    NodeStart {
        execution_id: String,
        node_id: String,
        node_type: String,
    },
    NodeDone {
        execution_id: String,
        node_id: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        output: Option<serde_json::Value>,
    },
    NodeError {
        execution_id: String,
        node_id: String,
        error: String,
    },
    NodeOutput {
        execution_id: String,
        node_id: String,
        output_key: String,
        data: serde_json::Value,
    },
    LlmToken {
        execution_id: String,
        node_id: String,
        token: String,
    },
    ExecutionDone {
        execution_id: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        result: Option<serde_json::Value>,
        #[serde(skip_serializing_if = "Option::is_none")]
        error: Option<String>,
    },
    Status {
        queue_length: usize,
        running_count: usize,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsSubmit {
    pub workflow: WorkflowJson,
    #[serde(default)]
    pub task_input: Option<serde_json::Value>,
}
