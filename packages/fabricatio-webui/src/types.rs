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
    /// MRO owner class name for grouped rendering of config fields (Python
    /// registry only; absent for legacy registries — frontend falls back to
    /// flat rendering).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group: Option<String>,
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
    /// 8-hex content fingerprint from the Python registry (registry.py
    /// `build_node_registry`), used for change detection. Absent when the
    /// registry did not provide it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schema_version: Option<String>,
    /// Raw Python source for the read-only source viewer.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_code: Option<String>,
}

/// One package-defined blueprint offered by the board sidebar (derived from
/// the package `workflows` modules — see python/fabricatio_webui/blueprints.py).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlueprintJson {
    pub id: String,
    pub name: String,
    pub description: String,
    pub category: String,
    pub node_count: u32,
    /// The workflow document dropped onto a role when this blueprint is used.
    pub workflow: WorkflowJson,
}

// ── Board JSON (format_version 2: role-driven documents) ────────────────────

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
pub struct ActionFieldJson {
    pub name: String,
    #[serde(rename = "type")]
    pub field_type: String,
    #[serde(default)]
    pub optional: bool,
    #[serde(default)]
    pub default: Option<serde_json::Value>,
    #[serde(default)]
    pub widget: Option<String>,
}

/// A user-defined Action definition; code-gen emits an Action subclass.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionDefJson {
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub fields: Vec<ActionFieldJson>,
    #[serde(default)]
    pub capabilities: Vec<String>,
    #[serde(default)]
    pub output_key: String,
    #[serde(default)]
    pub ctx_override: bool,
}

/// One workflow inside a role: a graph plus its namespace subscription.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowJson {
    #[serde(default)]
    pub name: Option<String>,
    /// Plain namespace ("write::book") the workflow subscribes to; the
    /// subscription pattern is derived as "<namespace>::*::Pending".
    #[serde(default)]
    pub namespace: Option<String>,
    /// Context key extracted as the task output; defaults to the last node's
    /// output key when absent.
    #[serde(default)]
    pub task_output_key: Option<String>,
    #[serde(default)]
    pub nodes: Vec<FabricatioNode>,
    #[serde(default)]
    pub edges: Vec<FabricatioEdge>,
    #[serde(default)]
    pub init_context: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleJson {
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub workflows: Vec<WorkflowJson>,
}

/// Top-level saved document: a board holding roles, their workflows, and
/// board-level custom action definitions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoardJson {
    pub version: String,
    /// Board format version; 2 = role-driven boards (0/1 = legacy workflows).
    #[serde(default)]
    pub format_version: u32,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub roles: Vec<RoleJson>,
    #[serde(default)]
    pub actions: Vec<ActionDefJson>,
    #[serde(default)]
    pub meta: Option<WorkflowMeta>,
}

impl BoardJson {
    /// Upgrade a legacy (format_version < 2) workflow document into a board
    /// holding one role with one workflow. Boards pass through unchanged.
    pub fn migrate_legacy(value: serde_json::Value) -> serde_json::Value {
        let Some(mut obj) = value.as_object().cloned() else {
            return value;
        };
        let fv = obj
            .get("format_version")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        if obj.contains_key("roles") || fv >= 2 {
            return serde_json::Value::Object(obj);
        }

        let name = obj.get("name").cloned();
        let description = obj.get("description").cloned();
        let meta = obj.get("meta").cloned();

        let mut wf = serde_json::Map::new();
        wf.insert(
            "name".into(),
            name.clone().unwrap_or(serde_json::Value::Null),
        );
        wf.insert(
            "namespace".into(),
            name.clone().unwrap_or(serde_json::Value::Null),
        );
        wf.insert(
            "nodes".into(),
            obj.remove("nodes").unwrap_or_else(|| serde_json::json!([])),
        );
        wf.insert(
            "edges".into(),
            obj.remove("edges").unwrap_or_else(|| serde_json::json!([])),
        );
        wf.insert(
            "init_context".into(),
            obj.remove("init_context")
                .unwrap_or_else(|| serde_json::json!({})),
        );

        let mut role = serde_json::Map::new();
        role.insert(
            "name".into(),
            serde_json::Value::String(
                name.clone()
                    .and_then(|v| v.as_str().map(String::from))
                    .unwrap_or_else(|| "Role".into()),
            ),
        );
        role.insert(
            "description".into(),
            description.unwrap_or_else(|| serde_json::json!("")),
        );
        role.insert(
            "workflows".into(),
            serde_json::json!([serde_json::Value::Object(wf)]),
        );

        let mut board = serde_json::Map::new();
        board.insert("version".into(), serde_json::json!("1.0"));
        board.insert("format_version".into(), serde_json::json!(2));
        board.insert(
            "name".into(),
            name.unwrap_or_else(|| serde_json::json!("Untitled Board")),
        );
        board.insert(
            "roles".into(),
            serde_json::json!([serde_json::Value::Object(role)]),
        );
        board.insert("actions".into(), serde_json::json!([]));
        if let Some(m) = meta {
            board.insert("meta".into(), m);
        }
        serde_json::Value::Object(board)
    }
}

// ── Execution ────────────────────────────────────────────────────────────────

/// Task-shaped execution payload — pure namespace dispatch (format v2).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskJson {
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub goals: Vec<String>,
    #[serde(default)]
    pub dependencies: Vec<String>,
    /// Namespace path components; the published event is
    /// "<send_to>::*::Pending" and matching workflows serve the task.
    #[serde(default)]
    pub send_to: Vec<String>,
    #[serde(default)]
    pub extra_init_context: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionRequest {
    pub task: TaskJson,
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
    fn node_type_definition_schema_version_round_trips() {
        let raw = r#"{"type":"Foo","title":"Foo","description":"","category":"general",
            "input_ports":[],"output_ports":[],"capabilities":[],
            "ctx_override":false,"config_fields":[],"schema_version":"a1b2c3d4"}"#;
        let n: NodeTypeDefinition = serde_json::from_str(raw).unwrap();
        assert_eq!(n.schema_version.as_deref(), Some("a1b2c3d4"));
        let s = serde_json::to_string(&n).unwrap();
        assert!(s.contains(r#""schema_version":"a1b2c3d4""#));
    }

    #[test]
    fn node_type_definition_schema_version_absent_defaults_none_and_is_skipped() {
        let raw = r#"{"type":"Foo","title":"Foo","description":"","category":"general",
            "input_ports":[],"output_ports":[],"capabilities":[],
            "ctx_override":false,"config_fields":[]}"#;
        let n: NodeTypeDefinition = serde_json::from_str(raw).unwrap();
        assert!(n.schema_version.is_none());
        let s = serde_json::to_string(&n).unwrap();
        assert!(!s.contains("schema_version"));
    }

    #[test]
    fn legacy_workflow_migrates_to_board_with_single_role() {
        let raw = r#"{"version":"1.0","format_version":1,"name":"legacy","nodes":[],"edges":[],"init_context":{}}"#;
        let value: serde_json::Value = serde_json::from_str(raw).unwrap();
        let board: BoardJson = serde_json::from_value(BoardJson::migrate_legacy(value)).unwrap();
        assert_eq!(board.format_version, 2);
        assert_eq!(board.name.as_deref(), Some("legacy"));
        assert_eq!(board.roles.len(), 1);
        assert_eq!(board.roles[0].name, "legacy");
        assert_eq!(board.roles[0].workflows.len(), 1);
        assert_eq!(
            board.roles[0].workflows[0].namespace.as_deref(),
            Some("legacy")
        );
        assert!(board.roles[0].workflows[0].nodes.is_empty());
        assert!(board.actions.is_empty());
    }

    #[test]
    fn board_passes_through_migration_unchanged() {
        let raw = r#"{"version":"1.0","format_version":2,"name":"b","roles":[{"name":"r","workflows":[]}],"actions":[]}"#;
        let value: serde_json::Value = serde_json::from_str(raw).unwrap();
        let migrated = BoardJson::migrate_legacy(value);
        assert!(migrated.get("roles").is_some());
        let board: BoardJson = serde_json::from_value(migrated).unwrap();
        assert_eq!(board.roles[0].name, "r");
    }

    #[test]
    fn board_workflow_defaults_namespace_and_output_key_none() {
        let raw = r#"{"name":"w","nodes":[],"edges":[]}"#;
        let wf: WorkflowJson = serde_json::from_str(raw).unwrap();
        assert_eq!(wf.name.as_deref(), Some("w"));
        assert!(wf.namespace.is_none());
        assert!(wf.task_output_key.is_none());
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
    fn port_group_round_trip() {
        let raw = r#"{"name":"llm_send_to","type":"str","optional":true,
            "default":null,"group":"LLMScopedConfig"}"#;
        let p: PortDefinition = serde_json::from_str(raw).unwrap();
        assert_eq!(p.group.as_deref(), Some("LLMScopedConfig"));
        // serialising back includes the field
        let s = serde_json::to_string(&p).unwrap();
        assert!(
            s.contains(r#""group":"LLMScopedConfig""#),
            "serialised: {s}"
        );
    }

    #[test]
    fn port_group_absent_defaults_none() {
        // no group key → None (skip_serializing_if None means it is absent)
        let raw = r#"{"name":"own_field","type":"str","optional":false}"#;
        let p: PortDefinition = serde_json::from_str(raw).unwrap();
        assert!(p.group.is_none());
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
        let raw = r#"{"type":"execution_done","execution_id":"e1","cancelled":true}"#;
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
