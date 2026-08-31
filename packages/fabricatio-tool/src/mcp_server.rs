use error_mapping::AsPyErr;
use mcp_server::{ServerError, ToolHandler, ToolServer};
use pyo3::Bound;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyModule};
use pyo3_async_runtimes::tokio::future_into_py;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use pythonize::depythonize;
use rmcp::model::{CallToolResult, ContentBlock, JsonObject};
use serde_json::Value;
use std::sync::Arc;

/// Python-exposed MCP server exposing Python callables as MCP tools.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct MCPServer {
    inner: Arc<ToolServer>,
}

/// Build the keyword arguments dict for a tool invocation.
fn build_kwargs(py: Python<'_>, arguments: Option<JsonObject>) -> PyResult<Bound<'_, PyDict>> {
    let kwargs = PyDict::new(py);
    if let Some(object) = arguments {
        let dict = pythonize::pythonize(py, &object)
            .into_pyresult()?
            .cast_into::<PyDict>()?;
        kwargs.update(dict.as_any().cast::<pyo3::types::PyMapping>()?)?;
    }
    Ok(kwargs)
}

/// Convert a tool return value to text: `str` verbatim, anything else via
/// `json.dumps`.
fn value_to_text(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<String> {
    if let Ok(text) = value.extract::<String>() {
        return Ok(text);
    }
    let json = PyModule::import(py, "json")?;
    let dumped = json.call_method1("dumps", (value,))?;
    dumped.extract::<String>()
}

/// Render a Python exception as a tool-level error result. Tool failures are
/// surfaced to the MCP caller as content with `is_error: true`, never as a
/// Rust protocol error.
fn exception_result(error: PyErr) -> CallToolResult {
    CallToolResult::error(vec![ContentBlock::text(format!("{error:?}"))])
}

/// Convert a successfully called Python value into a tool result.
fn success_result(value: Py<PyAny>) -> CallToolResult {
    match Python::attach(|py| value_to_text(py, value.bind(py))) {
        Ok(text) => CallToolResult::success(vec![ContentBlock::text(text)]),
        Err(error) => exception_result(error),
    }
}

/// Build the boxed handler bridging an `mcp-server` tool call back into
/// Python. Both sync and async functions run on a blocking worker; async
/// functions are awaited with a fresh `asyncio.run` loop so they work on
/// tokio worker threads that never host a Python event loop.
///
/// `Py<PyAny>` is not `Clone` without the `py-clone` feature, so the callable
/// is wrapped in an `Arc` and re-referenced per call via `clone_ref` under the
/// GIL.
fn make_handler(func: Py<PyAny>, is_async: bool) -> ToolHandler {
    let func = Arc::new(func);
    Arc::new(move |arguments: Option<JsonObject>| {
        let func = func.clone();
        Box::pin(async move {
            let func = Python::attach(|py| func.clone_ref(py));
            let called = tokio::task::spawn_blocking(move || {
                Python::attach(|py| -> PyResult<Py<PyAny>> {
                    let kwargs = build_kwargs(py, arguments)?;
                    let result = func.call(py, (), Some(&kwargs))?;
                    if is_async {
                        let asyncio = PyModule::import(py, "asyncio")?;
                        Ok(asyncio.call_method1("run", (result,))?.unbind())
                    } else {
                        Ok(result)
                    }
                })
            })
            .await;
            match called {
                Ok(Ok(value)) => Ok(success_result(value)),
                Ok(Err(error)) => Ok(exception_result(error)),
                Err(error) => Ok(CallToolResult::error(vec![ContentBlock::text(format!(
                    "{error}"
                ))])),
            }
        })
    })
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl MCPServer {
    /// Creates a new MCP server with the given identity.
    ///
    /// Args:
    ///     name: The server name advertised to clients.
    ///     version: The server version advertised to clients.
    ///     instructions: Optional server guidance surfaced to clients.
    ///
    /// Returns:
    ///     A new MCPServer instance.
    #[staticmethod]
    fn create(name: String, version: String, instructions: Option<String>) -> Self {
        Self {
            inner: Arc::new(ToolServer::new(name, version, instructions)),
        }
    }

    /// Registers a Python callable as an MCP tool.
    ///
    /// Args:
    ///     name: The tool name; registering an existing name replaces it.
    ///     description: The tool description advertised to clients.
    ///     schema: The JSON input schema as a Python dict.
    ///     func: The Python callable to invoke. Async functions are awaited;
    ///         sync functions run on a worker thread. Return values are
    ///         rendered as text: `str` verbatim, anything else via
    ///         `json.dumps`. Raised exceptions surface as tool errors.
    ///
    /// Returns:
    ///     None on success.
    fn add_tool(
        &self,
        name: String,
        description: String,
        schema: Bound<'_, PyAny>,
        func: Py<PyAny>,
    ) -> PyResult<()> {
        let schema_json: Value = depythonize(&schema).into_pyresult()?;
        let is_async = Python::attach(|py| -> PyResult<bool> {
            let inspect = PyModule::import(py, "inspect")?;
            let checker = inspect.getattr("iscoroutinefunction")?;
            let flag = checker.call1((func.bind(py),))?;
            flag.extract::<bool>()
        })?;
        self.inner
            .register(name, description, schema_json, make_handler(func, is_async))
            .map_err(|e: ServerError| PyRuntimeError::new_err(e.to_string()))
    }

    /// Removes a registered tool.
    ///
    /// Args:
    ///     name: The tool name to remove.
    ///
    /// Returns:
    ///     True if a tool with that name was registered.
    fn remove_tool(&self, name: String) -> bool {
        self.inner.unregister(&name)
    }

    /// Lists the names of all registered tools.
    ///
    /// Returns:
    ///     A list of tool names.
    fn list_tools(&self) -> Vec<String> {
        self.inner.list_tools()
    }

    #[getter]
    /// Returns the URL of the running HTTP server, if started.
    ///
    /// Returns:
    ///     The server URL or None.
    fn url(&self) -> Option<String> {
        self.inner.url()
    }

    /// Serves over streamable HTTP on the given host and port.
    ///
    /// Args:
    ///     host: The interface to bind (e.g. "127.0.0.1").
    ///     port: The port to bind; 0 picks an ephemeral port.
    ///
    /// Returns:
    ///     An awaitable resolving to the server URL once the listener is
    ///     bound; the server task keeps running.
    fn serve_http<'a>(
        &self,
        python: Python<'a>,
        host: String,
        port: u16,
    ) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            inner
                .serve_http(&host, port)
                .await
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Serves over stdio until the stream closes.
    ///
    /// Returns:
    ///     An awaitable that resolves when the stdio server exits.
    fn serve_stdio<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            inner
                .serve_stdio()
                .await
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Stops all running server tasks.
    ///
    /// Returns:
    ///     An awaitable that resolves once the tasks are aborted.
    fn shutdown<'a>(&self, python: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(python, async move {
            inner.shutdown().await;
            Ok(())
        })
    }
}

/// Registers the MCP server classes with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MCPServer>()?;
    Ok(())
}
