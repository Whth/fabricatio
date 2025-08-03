use futures::future::join_all;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::{Bound, PyResult, Python};
use pyo3_async_runtimes::tokio::future_into_py;
use pythonize::{depythonize, pythonize};
use rmcp::model::Tool;
use rmcp::service::{DynService, RunningService};
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

#[derive(Debug)]
pub enum McpError {
    IoError(std::io::Error),
    RmcpError(Box<dyn Error + Send + Sync>),
    ClientNotFound(String),
    ServiceError(String),
}

#[derive(Debug, Serialize, Deserialize)]
enum Transport {
    Stdio,
    Sse,
}

#[derive(Debug, Serialize, Deserialize)]
struct ServiceConfig {
    #[serde(rename = "type")]
    service_type: Transport,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    command: Option<String>,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    url: Option<String>,

    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    args: Vec<String>,

    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    env: HashMap<String, Value>,
}

#[derive(Debug, Serialize, Deserialize)]
struct MCPConfig {
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
        McpError::IoError(error)
    }
}

pub type Result<T> = std::result::Result<T, McpError>;

pub struct McpManagerInner {
    clients: HashMap<String, RunningService<RoleClient, Box<dyn DynService<RoleClient>>>>,
}

impl McpManagerInner {
    fn new(config: MCPConfig) -> Result<Self> {
        let mut clients = HashMap::new();
        let mut fut = vec![];
        for (name, config) in config.servers.iter() {
            let service_fut = match config.service_type {
                Transport::Stdio if config.command.is_some() => {
                    let cmd_str = config.command.as_ref().unwrap();

                    ().into_dyn().serve(TokioChildProcess::new(
                        Command::new(OsStr::new(cmd_str)).configure(|cmd| {
                            cmd.args(config.args.iter().map(OsStr::new));
                        }),
                    )?)
                }
                Transport::Sse => {
                    todo!()
                }

                _ => {
                    return Err(McpError::ServiceError("Invalid service type".to_string()));
                }
            };

            fut.push((name, service_fut));
        }

        tokio::runtime::Runtime::new()?.block_on(async {
            let mut futures = Vec::new();
            let mut names = Vec::new();

            // 提前收集名字和 future
            for (name, fut) in fut {
                names.push(name.to_owned());
                futures.push(fut);
            }

            // 并发执行所有 future
            let results = join_all(futures).await;

            // 处理结果
            for (name, result) in names.into_iter().zip(results) {
                let service = result.map_err(|e| McpError::RmcpError(Box::new(e)))?;
                clients.insert(name, service);
            }

            Ok::<(), McpError>(()) // 注意：这里要处理 Result 的传播
        })?;

        Ok(Self { clients })
    }
    pub async fn list_tools(&self, client_id: &str) -> Result<Vec<rmcp::model::Tool>> {
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

#[pyclass]
struct McpManager {
    inner: Arc<McpManagerInner>,
}

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
    fn dump_dict<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        pythonize(python, &self.inner).map_err(move |e| PyRuntimeError::new_err(e.to_string()))
    }
}

#[pymethods]
impl McpManager {
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

    fn list_tools<'a>(&self, python: Python<'a>, client_id: String) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();

        future_into_py(python, async move {
            // Use move to capture the cloned data
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
            // Use move to capture the cloned data
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

/// Registers the gather_violations function with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<McpManager>()?;
    m.add_class::<ToolMetaData>()?;
    Ok(())
}
