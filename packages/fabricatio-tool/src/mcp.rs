use futures::future::{BoxFuture, join_all};
use futures::{FutureExt, TryFutureExt};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::{Bound, PyResult, Python};
use pyo3_async_runtimes::tokio::future_into_py;
use pythonize::{depythonize, pythonize};
use rmcp::model::Tool;
use rmcp::service::{DynService, RunningService};
use rmcp::transport::{SseClientTransport, StreamableHttpClientTransport, WorkerTransport};
use rmcp::{
    RoleClient,
    model::CallToolRequestParam,
    service::ServiceExt,
    transport::{ConfigureCommandExt, TokioChildProcess},
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::error::Error;
use std::ffi::OsStr;
use std::fmt;
use std::sync::Arc;
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
struct ServiceConfig {
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
struct MCPConfig {
    /// Map of server names to their configurations
    servers: HashMap<String, ServiceConfig>,
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
pub struct McpManagerInner {
    /// Map of client IDs to their running services
    clients: HashMap<String, MCPService>,
}

type ClientFuture<'a> = BoxFuture<'a, Result<MCPService>>;
impl McpManagerInner {
    /// Creates a new MCP manager from configuration
    fn new(config: MCPConfig) -> Result<Self> {
        let mut clients = HashMap::new();
        let fut = config
            .servers
            .iter()
            .map(|(name, config)| {
                let fut = match config.service_type {
                    Transport::Stdio if config.command.is_some() => {
                        Self::make_stdio_client_future(config)
                    }
                    Transport::Sse if config.url.is_some() => Self::make_sse_client_future(config),
                    Transport::Stream if config.url.is_some() => {
                        let url = config.url.as_ref().unwrap();
                        ().into_dyn()
                            .serve(StreamableHttpClientTransport::from_uri(url.clone()))
                            .map_err(|e| McpError::ServiceError(e.to_string()))
                            .boxed()
                    }
                    Transport::Worker if config.url.is_some() => {
                        let url = config.url.as_ref().unwrap();
                        ().into_dyn()
                            .serve(WorkerTransport::from_uri(url.clone()))
                            .map_err(|e| McpError::ServiceError(e.to_string()))
                            .boxed()
                    }
                    _ => async { Err(McpError::ServiceError("Invalid service type".to_string())) }
                        .boxed(),
                };
                (name, fut)
            })
            .collect::<Vec<_>>();

        tokio::runtime::Runtime::new()?.block_on(async {
            let mut futures = Vec::new();
            let mut names = Vec::new();

            // Collect names and futures upfront
            for (name, fut) in fut {
                names.push(name.to_owned());
                futures.push(fut);
            }

            // Execute all futures concurrently
            let results = join_all(futures).await;

            // Process results
            for (name, result) in names.into_iter().zip(results) {
                let service = result.map_err(|e| McpError::RmcpError(Box::new(e)))?;
                clients.insert(name, service);
            }

            Ok::<(), McpError>(())
        })?;

        Ok(Self { clients })
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

/// Python-exposed MCP manager
#[pyclass]
struct McpManager {
    inner: Arc<McpManagerInner>,
}

/// Python representation of tool metadata
#[pyclass]
struct ToolMetaData {
    inner: Tool,
}

impl From<Tool> for ToolMetaData {
    fn from(value: Tool) -> Self {
        Self { inner: value }
    }
}

#[pymethods]
impl ToolMetaData {
    /// Serializes the tool metadata to a Python dictionary
    fn dump_dict<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        pythonize(python, &self.inner).map_err(move |e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[pymethods]
impl McpManager {
    /// Creates a new MCP manager instance
    ///
    /// # Arguments
    /// * `server_configs` - Python dictionary containing server configurations
    #[new]
    fn new(server_configs: Bound<'_, PyDict>) -> PyResult<Self> {
        Ok(Self {
            inner: Arc::new(
                McpManagerInner::new(MCPConfig {
                    servers: depythonize::<HashMap<String, ServiceConfig>>(&server_configs)
                        .map_err(move |e| PyRuntimeError::new_err(e.to_string()))?,
                })
                .map_err(move |e| PyRuntimeError::new_err(e.to_string()))?,
            ),
        })
    }

    /// Retrieves list of tools from a client
    fn list_tools<'a>(&self, python: Python<'a>, client_id: String) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();

        future_into_py(python, async move {
            let tools = inner
                .list_tools(client_id.as_str())
                .await
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            Ok(tools
                .into_iter()
                .map(ToolMetaData::from)
                .collect::<Vec<_>>())
        })
    }

    fn server_list(&self) -> Vec<String> {
        self.inner.server_list()
    }

    fn server_count(&self) -> usize {
        self.inner.server_count()
    }
    /// Executes a tool on a client and returns the result
    fn call_tool<'a>(
        &self,
        python: Python<'a>,
        client_id: String,
        tool_name: String,
        arguments: Option<Bound<'_, PyDict>>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();

        let arguments = if let Some(arguments) = arguments {
            let arguments = depythonize::<serde_json::Map<String, Value>>(&arguments)
                .map_err(move |e| PyRuntimeError::new_err(e.to_string()))?;
            Some(arguments)
        } else {
            None
        };

        future_into_py(python, async move {
            let result = inner
                .call_tool(client_id.as_str(), tool_name.as_str(), arguments)
                .await
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            Ok(result
                .content
                .into_iter()
                .map(|c| c.raw.as_text().unwrap().text.clone())
                .collect::<Vec<_>>())
        })
    }
}

/// Registers Python module components
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<McpManager>()?;
    m.add_class::<ToolMetaData>()?;
    Ok(())
}
