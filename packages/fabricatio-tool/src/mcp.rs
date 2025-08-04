use mcp_manager::{MCPConfig, MCPManager as MCPManagerInner, ServiceConfig};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::{Bound, PyResult, Python};
use pyo3_async_runtimes::tokio::future_into_py;
use pythonize::{depythonize, pythonize};
use rmcp::model::Tool;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tracing_subscriber::prelude::*;

/// Python-exposed MCP manager
#[pyclass]
struct McpManager {
    inner: Arc<MCPManagerInner>,
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
                MCPManagerInner::new(MCPConfig {
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

    /// Returns a list of all server names currently managed by the MCP manager
    fn server_list(&self) -> Vec<String> {
        self.inner.server_list()
    }

    /// Returns the number of servers currently managed by the MCP manager
    fn server_count(&self) -> usize {
        self.inner.server_count()
    }

    /// Checks if a client is still connected and responsive
    ///
    /// # Arguments
    /// * `client_id` - The ID of the client to ping
    ///
    /// # Returns
    /// * `PyResult<bool>` - Ok(true) if the client is connected, Ok(false) if not, or an error if the client doesn't exist
    fn ping(&self, client_id: &str) -> PyResult<bool> {
        self.inner
            .ping(client_id)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))
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
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| format!("info,{}=debug", env!("CARGO_CRATE_NAME")).into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();
    m.add_class::<McpManager>()?;
    m.add_class::<ToolMetaData>()?;
    Ok(())
}
