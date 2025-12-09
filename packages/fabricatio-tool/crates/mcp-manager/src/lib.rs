mod error;

pub use error::McpError;
use error::McpError::RmcpError;
use futures::future::BoxFuture;
use futures::{stream, FutureExt, StreamExt, TryFutureExt};
use rmcp::model::{CallToolRequestParam, Tool};
use rmcp::service::{DynService, RunningService};
use rmcp::transport::child_process::TokioChildProcess;
use rmcp::transport::streamable_http_client::StreamableHttpClientTransport;
use rmcp::transport::worker::WorkerTransport;
use rmcp::transport::ConfigureCommandExt;
use rmcp::{RoleClient, ServiceExt};
use serde::{Deserialize, Serialize};
use serde_json::value::Value;
use std::collections::HashMap;
use std::default::Default;
use std::ffi::OsStr;
use std::fmt::Debug;
use tokio::process::Command;
use which::which;

/// Transport protocol types for service communication
#[derive(Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[derive(PartialEq)]
enum Transport {
    /// Standard input/output communication
    #[default]
    Stdio,
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

type MCPService = RunningService<RoleClient, Box<dyn DynService<RoleClient>>>;

/// Inner manager structure handling client connections
pub struct MCPManager {
    /// Map of client IDs to their running services
    clients: HashMap<String, MCPService>,
}

type ClientFuture<'a> = BoxFuture<'a, error::Result<MCPService>>;

impl MCPManager {
    /// Creates a new MCP manager from configuration
    pub async fn create(config: MCPConfig) -> Self {
        let clients = stream::iter(config.servers)
            .map(|(name, config)| async move {
                let serv_res = match config.service_type {
                    Transport::Stdio if config.command.is_some() => {
                        Self::make_stdio_client_future(&config).await
                    }
                    Transport::Stream if config.url.is_some() => {
                        ().into_dyn()
                            .serve(StreamableHttpClientTransport::from_uri(config.url.unwrap()))
                            .map_err(|e| McpError::ServiceInitError(e.to_string()))
                            .await
                    }
                    Transport::Worker if config.url.is_some() => {
                        ().into_dyn()
                            .serve(WorkerTransport::from_uri(config.url.unwrap()))
                            .map_err(|e| McpError::ServiceInitError(e.to_string()))
                            .await
                    }
                    _ => async { Err(McpError::ServiceNotSupportedError) }.await,
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

    fn make_stdio_client_future(config: &'_ ServiceConfig) -> ClientFuture<'_> {
        let cmd_str = config.command.as_ref().unwrap();

        let cmd = match which(cmd_str) {
            Ok(cmd_path) => Command::new(cmd_path.as_os_str()).configure(|cmd| {
                cmd.args(config.args.iter().map(OsStr::new));
                cmd.envs(config.env.iter().map(|(k, v)| {
                    let v = match v {
                        Value::String(s) => s.clone(),
                        _ => v.to_string(),
                    };
                    (k.clone(), v)
                }));
            }),
            Err(e) => return async move { Err(McpError::CommandNotFound(e)) }.boxed(),
        };

        match TokioChildProcess::new(cmd) {
            Ok(proc) => {
                ().into_dyn()
                    .serve(proc)
                    .map_err(|e| McpError::ServiceInitError(e.to_string()))
                    .boxed()
            }
            Err(e) => async move { Err(McpError::IoError(e)) }.boxed(),
        }
    }

    pub async fn ping(&self, client_id: &str) -> error::Result<bool> {
        self.clients
            .get(client_id)
            .ok_or(McpError::ClientNotFound(client_id.to_string()))?
            .list_tools(None)
            .await
            .map(|_| true)
            .map_err(RmcpError)
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
    pub async fn list_tools(&self, client_id: &str) -> error::Result<Vec<Tool>> {
        self.clients
            .get(client_id)
            .ok_or(McpError::ClientNotFound(client_id.to_owned()))
            .map(|client| async move { client.list_all_tools().await.map_err(RmcpError) })?
            .await
    }
    /// Retrieves a specific tool from a client by name
    ///
    /// # Arguments
    ///
    /// * `client_id` - The ID of the client to retrieve the tool from
    /// * `tool_name` - The name of the tool to retrieve
    ///
    /// # Returns
    ///
    /// * `Result<Tool>` - The requested tool if found, or an error if the client
    ///   doesn't exist, there's a communication issue, or the tool is not found
    pub async fn get_tool(&self, client_id: &str, tool_name: &str) -> error::Result<Tool> {
        self.clients
            .get(client_id)
            .ok_or(McpError::ClientNotFound(client_id.to_owned()))
            .map(|client| async move {
                client
                    .list_all_tools()
                    .await
                    .map_err(RmcpError)?
                    .into_iter()
                    .filter(|tool| tool.name == tool_name)
                    .last()
                    .ok_or(McpError::ToolNotFound(tool_name.to_string()))
            })?
            .await
    }
    /// Executes a tool on a client
    pub async fn call_tool(
        &self,
        client_id: &str,
        tool_name: &str,
        arguments: Option<serde_json::Map<String, Value>>,
    ) -> error::Result<rmcp::model::CallToolResult> {
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
            .map_err(RmcpError)
    }

    /// Checks if a client with the given ID exists in the manager
    pub fn has_client(&self, client_id: &str) -> bool {
        self.clients.contains_key(client_id)
    }

    /// Checks if a specific tool exists for a given client
    ///
    /// # Arguments
    ///
    /// * `client_id` - The ID of the client to check
    /// * `tool_name` - The name of the tool to look for
    ///
    /// # Returns
    ///
    /// * `Result<bool>` - Ok(true) if the tool exists, Ok(false) if it doesn't,
    ///   or an error if the client doesn't exist or there's a communication issue
    pub async fn has_tool(&self, client_id: &str, tool_name: &str) -> error::Result<bool> {
        self.clients
            .get(client_id)
            .map(|client| async move {
                client
                    .list_all_tools()
                    .await
                    .map(|tools| tools.iter().any(|t| t.name == tool_name))
                    .map_err(RmcpError)
            })
            .ok_or(McpError::ClientNotFound(client_id.to_owned()))?
            .await
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
        let client_not_found = McpError::ClientNotFound("test_client".to_string());
        assert_eq!(
            format!("{}", client_not_found),
            "Client test_client not found"
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
