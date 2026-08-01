use chrono::Utc;
use serde::{Deserialize, Serialize};

/// serde helper: skip a bool field when it is `false` (used for `cancelled`).
fn is_false(b: &bool) -> bool {
    !*b
}

// ── Node Registry ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortDefinition {
    pub name: String,
    #[serde(rename = "type")]
    pub port_type: String,
    pub optional: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    /// Widget hint for the frontend inline editor ("text", "number", "combo", "toggle", "json", ...).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub widget: Option<String>,
    /// Choice list for "combo" widgets.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub options: Option<Vec<String>>,
    /// Default value when the field is unset.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub step: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub placeholder: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub separator: Option<String>,
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
    /// Version of the node type's schema this node was saved against (0 = legacy).
    #[serde(default)]
    pub schema_version: u32,
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
    /// Workflow format version; 0 = legacy (pre-0.5.0) files.
    #[serde(default)]
    pub format_version: u32,
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

// Wire protocol types for /api/history; constructed by the Python worker.
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionStatus {
    pub execution_id: String,
    pub state: ExecutionState,
    #[serde(default)]
    pub current_node: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
}

#[allow(dead_code)]
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
        /// True when the execution was interrupted via /api/interrupt.
        #[serde(default, skip_serializing_if = "is_false")]
        cancelled: bool,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn legacy_workflow_round_trip_defaults_format_version_zero() {
        let raw = r#"{"version":"1.0","name":"legacy","nodes":[],"edges":[],"init_context":{}}"#;
        let wf: WorkflowJson = serde_json::from_str(raw).unwrap();
        assert_eq!(wf.format_version, 0);
        assert!(wf.nodes.is_empty());
    }

    #[test]
    fn node_round_trip_defaults_schema_version_zero() {
        let raw = r#"{"id":"n1","type":"Foo","inputs":{},"config":{}}"#;
        let n: FabricatioNode = serde_json::from_str(raw).unwrap();
        assert_eq!(n.schema_version, 0);
    }

    #[test]
    fn port_widget_metadata_round_trip() {
        let raw = r#"{"name":"model","type":"str","optional":false,
            "widget":"combo","options":["gpt-4o","gpt-4o-mini"],"default":"gpt-4o"}"#;
        let p: PortDefinition = serde_json::from_str(raw).unwrap();
        assert_eq!(p.widget.as_deref(), Some("combo"));
        assert_eq!(
            p.options.as_deref(),
            Some(&["gpt-4o".to_string(), "gpt-4o-mini".to_string()][..])
        );
        assert_eq!(p.default.as_ref().and_then(|v| v.as_str()), Some("gpt-4o"));
    }

    #[test]
    fn execution_done_cancelled_defaults_false() {
        let raw = r#"{"type":"execution_done","execution_id":"e1"}"#;
        let m: WsMessage = serde_json::from_str(raw).unwrap();
        match m {
            WsMessage::ExecutionDone { cancelled, .. } => assert!(!cancelled),
            other => panic!("unexpected variant {other:?}"),
        }
    }

    #[test]
    fn execution_done_cancelled_true_round_trips() {
        let raw =
            r#"{"type":"execution_done","execution_id":"e1","cancelled":true}"#;
        let m: WsMessage = serde_json::from_str(raw).unwrap();
        match m {
            WsMessage::ExecutionDone { cancelled, .. } => assert!(cancelled),
            other => panic!("unexpected variant {other:?}"),
        }
    }

    #[test]
    fn execution_done_cancelled_false_is_not_serialized() {
        let m = WsMessage::ExecutionDone {
            execution_id: "e1".into(),
            result: None,
            error: None,
            cancelled: false,
            timestamp: None,
        };
        let s = serde_json::to_string(&m).unwrap();
        assert!(!s.contains("cancelled"));
        assert!(s.contains(r#""type":"execution_done""#));
    }
}
