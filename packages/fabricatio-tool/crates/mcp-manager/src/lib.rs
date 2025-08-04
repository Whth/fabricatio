use futures::future::BoxFuture;
use futures::{FutureExt, StreamExt, TryFutureExt, stream};
use rmcp::model::{CallToolRequestParam, Tool};
use rmcp::service::{DynService, RunningService};
use rmcp::transport::ConfigureCommandExt;
use rmcp::transport::child_process::TokioChildProcess;
use rmcp::transport::sse_client::SseClientTransport;
use rmcp::transport::streamable_http_client::StreamableHttpClientTransport;
use rmcp::transport::worker::WorkerTransport;
use rmcp::{RoleClient, ServiceExt};
use serde::{Deserialize, Serialize};
use serde_json::value::Value;
use std::collections::HashMap;
use std::default::Default;
use std::error::Error;
use std::ffi::OsStr;
use std::fmt;
use std::fmt::Debug;
use tokio::process::Command;
use which::which;

/// Represents possible errors that can occur in MCP operations
#[derive(Debug)]
pub enum McpError {
    /// I/O related errors
    IoError(String),
    /// Errors originating from RMCP operations
    RmcpError(Box<dyn Error + Send + Sync>),
    /// Requested client not found
    ClientNotFound(String),
    /// General service errors
    ServiceError(String),
}

/// Transport protocol types for service communication
#[derive(Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[derive(PartialEq)]
enum Transport {
    /// Standard input/output communication
    #[default]
    Stdio,
    /// Server-Sent Events (SSE) protocol
    Sse,
    /// HTTP streaming transport protocol
    Stream,
    /// Web worker transport protocol
    Worker,
}

/// Configuration for a single service instance
#[derive(Debug, Serialize, Deserialize)]
pub struct ServiceConfig {
    /// Type of transport to use for this service
    #[serde(default, rename = "type")]
    service_type: Transport,

    /// Command to execute for stdio services
    #[serde(default, skip_serializing_if = "Option::is_none")]
    command: Option<String>,

    /// URL for SSE services
    #[serde(default, skip_serializing_if = "Option::is_none")]
    url: Option<String>,

    /// Command-line arguments for stdio services
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    args: Vec<String>,

    /// Environment variables for the service process
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    env: HashMap<String, Value>,
}

/// Top-level MCP configuration structure
#[derive(Debug, Serialize, Deserialize)]
pub struct MCPConfig {
    /// Map of server names to their configurations
    pub servers: HashMap<String, ServiceConfig>,
}

impl fmt::Display for McpError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            McpError::IoError(e) => write!(f, "IO error: {}", e),
            McpError::RmcpError(e) => write!(f, "RMCP error: {}", e),
            McpError::ClientNotFound(id) => write!(f, "Client {} not found", id),
            McpError::ServiceError(e) => write!(f, "Service error: {}", e),
        }
    }
}

impl Error for McpError {}

impl From<std::io::Error> for McpError {
    fn from(error: std::io::Error) -> Self {
        McpError::IoError(error.to_string())
    }
}

/// Result type alias for MCP operations
pub type Result<T> = std::result::Result<T, McpError>;
type MCPService = RunningService<RoleClient, Box<dyn DynService<RoleClient>>>;

/// Inner manager structure handling client connections
pub struct MCPManager {
    /// Map of client IDs to their running services
    clients: HashMap<String, MCPService>,
}

type ClientFuture<'a> = BoxFuture<'a, Result<MCPService>>;

impl MCPManager {
    /// Creates a new MCP manager from configuration
    pub async fn create(config: MCPConfig) -> Self {
        let clients = stream::iter(config.servers)
            .map(|(name, config)| async move {
                let serv_res = match config.service_type {
                    Transport::Stdio if config.command.is_some() => {
                        Self::make_stdio_client_future(&config).await
                    }
                    Transport::Sse if config.url.is_some() => {
                        Self::make_sse_client_future(&config).await
                    }
                    Transport::Stream if config.url.is_some() => {
                        ().into_dyn()
                            .serve(StreamableHttpClientTransport::from_uri(config.url.unwrap()))
                            .map_err(|e| McpError::ServiceError(e.to_string()))
                            .await
                    }
                    Transport::Worker if config.url.is_some() => {
                        ().into_dyn()
                            .serve(WorkerTransport::from_uri(config.url.unwrap()))
                            .map_err(|e| McpError::ServiceError(e.to_string()))
                            .await
                    }
                    _ => {
                        async { Err(McpError::ServiceError("Invalid service type".to_string())) }
                            .await
                    }
                };
                (name, serv_res)
            })
            .buffer_unordered(3)
            .filter_map(|(name, serv_res)| async {
                match serv_res {
                    Ok(serv) => Some((name, serv)),
                    _ => None,
                }
            })
            .collect::<HashMap<_, _>>()
            .await;

        Self { clients }
    }

    fn make_sse_client_future(config: &'_ ServiceConfig) -> ClientFuture<'_> {
        let url = config.url.as_ref().unwrap().clone();
        async move {
            match SseClientTransport::start(url).await {
                Ok(transport) => {
                    ().into_dyn()
                        .serve(transport)
                        .map_err(|e| McpError::ServiceError(e.to_string()))
                        .await
                }
                Err(_) => Err(McpError::ServiceError("Invalid SSE URL".to_string())),
            }
        }
        .boxed()
    }

    fn make_stdio_client_future(config: &'_ ServiceConfig) -> ClientFuture<'_> {
        let cmd_str = config.command.as_ref().unwrap();
        let cmd = if let Ok(cmd_path) = which(cmd_str) {
            Command::new(cmd_path.as_os_str()).configure(|cmd| {
                cmd.args(config.args.iter().map(OsStr::new));
                cmd.envs(config.env.iter().map(|(k, v)| {
                    let v = match v {
                        Value::String(s) => s.clone(),
                        _ => v.to_string(),
                    };
                    (k.clone(), v)
                }));
            })
        } else {
            return async move {
                Err(McpError::IoError(format!(
                    "Failed to find executable: {cmd_str}"
                )))
            }
            .boxed();
        };

        match TokioChildProcess::new(cmd) {
            Ok(proc) => {
                ().into_dyn()
                    .serve(proc)
                    .map_err(|e| McpError::ServiceError(e.to_string()))
                    .boxed()
            }
            Err(e) => async move {
                Err(McpError::ServiceError(format!(
                    "Failed to start service with command: {cmd_str}, {e}"
                )))
            }
            .boxed(),
        }
    }

    pub async fn ping(&self, client_id: &str) -> Result<bool> {
        self.clients
            .get(client_id)
            .ok_or(McpError::ClientNotFound(client_id.to_string()))?
            .list_tools(None)
            .await
            .map(|_| true)
            .map_err(|e| McpError::ServiceError(format!("Failed to ping service: {e}")))
    }

    /// Returns a list of all server names currently managed by the MCP manager
    pub fn server_list(&self) -> Vec<String> {
        self.clients.keys().cloned().collect()
    }

    /// Returns the number of servers currently managed by the MCP manager
    pub fn server_count(&self) -> usize {
        self.clients.len()
    }

    /// Lists available tools from a client
    pub async fn list_tools(&self, client_id: &str) -> Result<Vec<Tool>> {
        self.clients
            .get(client_id)
            .ok_or(McpError::ClientNotFound(client_id.to_owned()))
            .map(|client| async move {
                client
                    .list_tools(Default::default())
                    .await
                    .map(|tools| tools.tools)
                    .map_err(|e| McpError::RmcpError(Box::new(e)))
            })?
            .await
    }

    /// Executes a tool on a client
    pub async fn call_tool(
        &self,
        client_id: &str,
        tool_name: &str,
        arguments: Option<serde_json::Map<String, Value>>,
    ) -> Result<rmcp::model::CallToolResult> {
        self.clients
            .get(client_id)
            .ok_or(McpError::ClientNotFound(client_id.to_owned()))
            .map(|client| {
                client.call_tool(CallToolRequestParam {
                    name: tool_name.to_owned().into(),
                    arguments,
                })
            })?
            .await
            .map_err(|e| McpError::RmcpError(Box::new(e)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashMap;

    #[tokio::test]
    async fn test_mcp_manager_create_stdio_service() {
        let mut servers = HashMap::new();
        servers.insert(
            "test_stdio".to_string(),
            ServiceConfig {
                service_type: Transport::Stdio,
                command: Some("nonexist".to_string()),
                args: vec!["test".to_string()],
                url: None,
                env: HashMap::new(),
            },
        );

        let config = MCPConfig { servers };
        let manager = MCPManager::create(config).await;

        assert_eq!(manager.server_count(), 0);
    }

    #[tokio::test]
    async fn test_mcp_manager_create_invalid_service() {
        let mut servers = HashMap::new();
        servers.insert(
            "invalid_service".to_string(),
            ServiceConfig {
                service_type: Transport::Stdio,
                command: None,
                args: vec![],
                url: None,
                env: HashMap::new(),
            },
        );

        let config = MCPConfig { servers };
        let manager = MCPManager::create(config).await;

        assert_eq!(manager.server_count(), 0);
        assert!(
            !manager
                .server_list()
                .contains(&"invalid_service".to_string())
        );
    }

    #[tokio::test]
    async fn test_mcp_manager_ping_nonexistent_client() {
        let servers = HashMap::new();
        let config = MCPConfig { servers };
        let manager = MCPManager::create(config).await;

        let result = manager.ping("nonexistent_client").await;
        assert!(result.is_err());
        match result.unwrap_err() {
            McpError::ClientNotFound(_) => (),
            _ => panic!("Expected ClientNotFound error"),
        }
    }

    #[tokio::test]
    async fn test_mcp_manager_list_tools_nonexistent_client() {
        let servers = HashMap::new();
        let config = MCPConfig { servers };
        let manager = MCPManager::create(config).await;

        let result = manager.list_tools("nonexistent_client").await;
        assert!(result.is_err());
        match result.unwrap_err() {
            McpError::ClientNotFound(_) => (),
            _ => panic!("Expected ClientNotFound error"),
        }
    }

    #[tokio::test]
    async fn test_mcp_manager_call_tool_nonexistent_client() {
        let servers = HashMap::new();
        let config = MCPConfig { servers };
        let manager = MCPManager::create(config).await;

        let result = manager
            .call_tool("nonexistent_client", "test_tool", None)
            .await;
        assert!(result.is_err());
        match result.unwrap_err() {
            McpError::ClientNotFound(_) => (),
            _ => panic!("Expected ClientNotFound error"),
        }
    }

    #[test]
    fn test_mcp_error_display() {
        let io_error = McpError::IoError("test io error".to_string());
        assert_eq!(format!("{}", io_error), "IO error: test io error");

        let rmcp_error = McpError::RmcpError("test rmcp error".into());
        assert_eq!(format!("{}", rmcp_error), "RMCP error: test rmcp error");

        let client_not_found = McpError::ClientNotFound("test_client".to_string());
        assert_eq!(
            format!("{}", client_not_found),
            "Client test_client not found"
        );

        let service_error = McpError::ServiceError("test service error".to_string());
        assert_eq!(
            format!("{}", service_error),
            "Service error: test service error"
        );
    }

    #[test]
    fn test_transport_default() {
        let transport: Transport = Default::default();
        assert_eq!(transport, Transport::Stdio);
    }

    #[test]
    fn test_service_config_serialization() {
        let config = ServiceConfig {
            service_type: Transport::Stdio,
            command: Some("test_cmd".to_string()),
            args: vec!["arg1".to_string(), "arg2".to_string()],
            url: None,
            env: {
                let mut map = HashMap::new();
                map.insert("TEST_ENV".to_string(), json!("test_value"));
                map
            },
        };

        let serialized = serde_json::to_string(&config).unwrap();
        let deserialized: ServiceConfig = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.service_type, Transport::Stdio);
        assert_eq!(deserialized.command, Some("test_cmd".to_string()));
        assert_eq!(
            deserialized.args,
            vec!["arg1".to_string(), "arg2".to_string()]
        );
        assert_eq!(deserialized.url, None);
        assert_eq!(deserialized.env.get("TEST_ENV"), Some(&json!("test_value")));
    }
}
