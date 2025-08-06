use mcp_manager::{MCPConfig, MCPManager as MCPManagerInner, ServiceConfig};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::{Bound, PyResult, Python};
use pyo3_async_runtimes::tokio::future_into_py;
use pythonize::{depythonize, pythonize};
use rmcp::model::{CallToolResult, Tool};
use serde_json::Value;
use signify::{schema_to_docstring_args, schema_to_signature};
use std::collections::HashMap;
use std::sync::Arc;

/// Python-exposed MCP manager
#[pyclass]
struct MCPManager {
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

    #[getter]
    fn name(&self) -> String {
        self.inner.name.to_string()
    }

    #[getter]
    fn description(&self) -> String {
        self.inner
            .description
            .clone()
            .unwrap_or_default()
            .to_string()
    }

    #[getter]
    fn input_schema<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        pythonize(python, &self.inner.input_schema)
            .map_err(move |e| PyRuntimeError::new_err(e.to_string()))
    }

    #[getter]
    fn input_schema_string(&self) -> String {
        serde_json::to_string(&self.inner.input_schema).unwrap_or_default()
    }

    #[getter]
    fn annotations<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        pythonize(python, &self.inner.annotations)
            .map_err(move |e| PyRuntimeError::new_err(e.to_string()))
    }
    #[getter]
    fn annotations_string(&self) -> String {
        serde_json::to_string(&self.inner.annotations).unwrap_or_default()
    }

    #[getter]
    fn function_header(&self) -> PyResult<String> {
        let inner = &self.inner;
        Ok(format!(
            "async def {}{}->list[str]:",
            inner.name,
            schema_to_signature(
                &serde_json::to_value(inner.clone().input_schema)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
            )
            .ok_or(PyRuntimeError::new_err("Invalid input schema"))?
        ))
    }
    #[getter]
    fn function_docstring(&self) -> PyResult<String> {
        let inner = &self.inner;
        Ok(format!(
            "{}\n{}\nReturn:\n    list[str]: The strings of execution info.",
            inner.clone().description.unwrap_or_default(),
            schema_to_docstring_args(
                &serde_json::to_value(inner.clone().input_schema)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
            )
            .unwrap_or_default()
        ))
    }
    #[getter]
    fn function_string(&self) -> PyResult<String> {
        let header = self.function_header()?;
        let docstring = self
            .function_docstring()?
            .lines()
            .map(|s| format!("    {}", s))
            .collect::<Vec<String>>()
            .join("\n");
        Ok(format!("{}\n    \"\"\"\n{}\n    \"\"\"", header, docstring))
    }
}

#[pymethods]
impl MCPManager {
    /// Creates a new MCP manager instance
    ///
    /// # Arguments
    /// * `server_configs` - Python dictionary containing server configurations
    #[staticmethod]
    fn create<'a>(
        python: Python<'a>,
        server_configs: Bound<'a, PyDict>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let conf = MCPConfig {
            servers: depythonize::<HashMap<String, ServiceConfig>>(&server_configs)
                .map_err(move |e| PyRuntimeError::new_err(e.to_string()))?,
        };
        future_into_py(python, async move {
            Ok(Self {
                inner: Arc::new(MCPManagerInner::create(conf).await),
            })
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

    /// Retrieves a tool from a client
    fn get_tool<'a>(
        &self,
        python: Python<'a>,
        client_id: String,
        tool_name: String,
    ) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            Ok(inner
                .get_tool(client_id.as_str(), tool_name.as_str())
                .await
                .ok()
                .map(ToolMetaData::from))
        })
    }

    /// Retrieves a list of tool names from a client
    ///
    /// # Arguments
    /// * `client_id` - The ID of the client to retrieve tools from
    ///
    /// # Returns
    /// * `PyResult<Vec<String>>` - A list of tool names or an error if the operation fails
    fn list_tool_names<'a>(
        &self,
        python: Python<'a>,
        client_id: String,
    ) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            match inner.list_tools(client_id.as_str()).await {
                Ok(tools) => Ok(tools
                    .into_iter()
                    .map(|tool| tool.name.to_string())
                    .collect::<Vec<_>>()),
                Err(e) => Err(PyRuntimeError::new_err(e.to_string())),
            }
        })
    }

    /// Retrieves a mapping of tool names to their descriptions from a client
    ///
    /// # Arguments
    /// * `client_id` - The ID of the client to retrieve tools from
    ///
    /// # Returns
    /// * `PyResult<HashMap<String, String>>` - A mapping of tool names to descriptions or an error if the operation fails
    fn description_mapping<'a>(
        &self,
        python: Python<'a>,
        client_id: String,
    ) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            match inner.list_tools(client_id.as_str()).await {
                Ok(tools) => Ok(tools
                    .into_iter()
                    .map(|tool| {
                        (
                            tool.name.to_string(),
                            tool.description.unwrap_or_default().to_string(),
                        )
                    })
                    .collect::<HashMap<String, String>>()),
                Err(e) => Err(PyRuntimeError::new_err(e.to_string())),
            }
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
    fn ping<'a>(&self, python: Python<'a>, client_id: String) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            inner
                .ping(&client_id)
                .await
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        })
    }
    /// Executes a tool on a client and returns the result
    fn call_tool<'a>(
        &self,
        python: Python<'a>,
        client_id: String,
        tool_name: String,
        arguments: Option<Bound<'_, PyDict>>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let arguments = if let Some(arguments) = arguments {
            let arguments = depythonize::<serde_json::Map<String, Value>>(&arguments)
                .map_err(move |e| PyRuntimeError::new_err(e.to_string()))?;
            Some(arguments)
        } else {
            None
        };

        let inner = self.inner.clone();
        future_into_py(python, async move {
            let result: CallToolResult = inner
                .call_tool(client_id.as_str(), tool_name.as_str(), arguments)
                .await
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            Ok(result.content.map(|ve| {
                ve.into_iter()
                    .map(|v| v.raw.as_text().map(|t| t.text.clone()).unwrap_or_default())
                    .collect::<Vec<_>>()
            }))
        })
    }
}

/// Registers Python module components
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MCPManager>()?;
    m.add_class::<ToolMetaData>()?;
    Ok(())
}
