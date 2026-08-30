//! Pure-Rust MCP server: expose native functions as MCP tools over stdio or
//! streamable HTTP without any Python dependency.
//!
//! [`ToolServer`] owns a registry of dynamic tool handlers. Register a
//! [`ToolHandler`] closure with a name, description and JSON input schema,
//! then serve it to MCP clients over either transport. Tools can be
//! registered, replaced and removed at runtime; clients observing the server
//! receive `notifications/tools/list_changed` when the visible tool list
//! changes.

mod error;
mod handler;

pub use error::{Result, ServerError};
use futures::future::BoxFuture;
use handler::FabricatioService;
use rmcp::ServiceExt;
use rmcp::handler::server::tool::ToolRoute;
use rmcp::model::{CallToolResult, JsonObject, ServerInfo};
use rmcp::transport::streamable_http_server::session::local::LocalSessionManager;
use rmcp::transport::streamable_http_server::{StreamableHttpServerConfig, StreamableHttpService};
use std::sync::Arc;
use std::sync::RwLock;
use tokio::net::TcpListener;
use tokio::sync::Mutex;
use tokio::task::JoinHandle;

/// A boxed tool implementation.
///
/// Receives the tool arguments as parsed JSON (or `None` when the client
/// omitted them) and resolves to the tool result. Returning
/// [`ServerError`] surfaces as an MCP protocol error; tool-level failures
/// the caller should see are expressed as
/// [`CallToolResult::error`][rmcp::model::CallToolResult::error] inside the
/// `Ok` value instead.
pub type ToolHandler = Arc<
    dyn Fn(
            Option<JsonObject>,
        ) -> BoxFuture<'static, std::result::Result<CallToolResult, ServerError>>
        + Send
        + Sync,
>;

/// Shared state behind a [`ToolServer`], visible to every served connection.
pub struct ServerInner {
    info: ServerInfo,
    router: RwLock<rmcp::handler::server::tool::ToolRouter<FabricatioService>>,
    tasks: Mutex<Vec<JoinHandle<()>>>,
    url: RwLock<Option<String>>,
}

/// An MCP server exposing dynamically registered tools.
///
/// Nothing is served until a transport is started; the registry is populated
/// with [`register`][Self::register] either before or after serving begins.
pub struct ToolServer {
    inner: Arc<ServerInner>,
}

impl ToolServer {
    /// Create a server with the given identity. `instructions` is optional
    /// server guidance surfaced to clients during initialization.
    pub fn new(
        name: impl Into<String>,
        version: impl Into<String>,
        instructions: Option<String>,
    ) -> Self {
        let mut info = ServerInfo::default();
        info.server_info.name = name.into();
        info.server_info.version = version.into();
        info.instructions = instructions;
        Self {
            inner: Arc::new(ServerInner {
                info,
                router: RwLock::new(Default::default()),
                tasks: Mutex::new(Vec::new()),
                url: RwLock::new(None),
            }),
        }
    }

    /// Register a tool, replacing any existing route with the same name.
    ///
    /// `schema` must deserialize to a JSON object (the tool input schema).
    pub fn register(
        &self,
        name: impl Into<String>,
        description: impl Into<String>,
        schema: serde_json::Value,
        handler: ToolHandler,
    ) -> Result<()> {
        let name = name.into();
        let schema_obj: JsonObject = serde_json::from_value(schema)
            .map_err(|e| ServerError::InvalidSchema(name.clone(), e.to_string()))?;
        let attr = rmcp::model::Tool::new(name, description.into(), Arc::new(schema_obj));
        let route = ToolRoute::new_dyn(attr, move |context| {
            let handler = handler.clone();
            let arguments = context.arguments.clone();
            Box::pin(async move {
                handler(arguments)
                    .await
                    .map(CallToolResult::into)
                    .map_err(|e| rmcp::ErrorData::internal_error(e.to_string(), None))
            })
        });
        self.inner
            .router
            .write()
            .unwrap_or_else(|e| e.into_inner())
            .add_route(route);
        Ok(())
    }

    /// Remove a registered tool. Returns `true` if a route existed.
    pub fn unregister(&self, name: &str) -> bool {
        let mut router = self.inner.router.write().unwrap_or_else(|e| e.into_inner());
        let existed = router.has_route(name);
        router.remove_route(name);
        existed
    }

    /// List the names of all registered tools.
    pub fn list_tools(&self) -> Vec<String> {
        self.inner
            .router
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .list_all()
            .into_iter()
            .map(|tool| tool.name.to_string())
            .collect()
    }

    /// Serve over streamable HTTP on the given host/port.
    ///
    /// Port `0` binds an ephemeral port; the returned URL reports the real
    /// bound port. The server task runs on the current tokio runtime until
    /// [`shutdown`][Self::shutdown] is called.
    pub async fn serve_http(&self, host: &str, port: u16) -> Result<String> {
        let listener = TcpListener::bind((host, port)).await?;
        let addr = listener.local_addr()?;
        let url = format!("http://{host}:{}/mcp", addr.port());
        let inner = self.inner.clone();
        let handle = tokio::spawn(async move {
            let session_manager = Arc::new(LocalSessionManager::default());
            let service = StreamableHttpService::new(
                move || {
                    Ok(FabricatioService {
                        server: inner.clone(),
                    })
                },
                session_manager,
                StreamableHttpServerConfig::default(),
            );
            let app = axum::Router::new().route_service("/mcp", service);
            if let Err(e) = axum::serve(listener, app).await {
                tracing::error!("MCP HTTP server failed: {e}");
            }
        });
        self.inner.tasks.lock().await.push(handle);
        *self.inner.url.write().unwrap_or_else(|e| e.into_inner()) = Some(url.clone());
        Ok(url)
    }

    /// Serve over stdio (`stdin`/`stdout`), the classic MCP child-process
    /// transport. Resolves when the stream closes or the client disconnects.
    pub async fn serve_stdio(&self) -> Result<()> {
        let service = FabricatioService {
            server: self.inner.clone(),
        };
        let transport = (tokio::io::stdin(), tokio::io::stdout());
        let running = service
            .serve(transport)
            .await
            .map_err(|e| ServerError::ServerInitError(Box::new(e)))?;
        running
            .waiting()
            .await
            .map_err(|e| ServerError::TaskError(e.to_string()))?;
        Ok(())
    }

    /// The URL of the running HTTP server, if [`serve_http`][Self::serve_http]
    /// has been started.
    pub fn url(&self) -> Option<String> {
        self.inner
            .url
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    /// Abort all server tasks and forget the HTTP URL.
    pub async fn shutdown(&self) {
        let tasks = std::mem::take(&mut *self.inner.tasks.lock().await);
        for task in tasks {
            task.abort();
        }
        *self.inner.url.write().unwrap_or_else(|e| e.into_inner()) = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rmcp::model::{CallToolRequestParams, ContentBlock};
    use rmcp::service::ServiceExt;
    use rmcp::transport::streamable_http_client::StreamableHttpClientTransport;
    use serde_json::json;

    fn add_handler() -> ToolHandler {
        Arc::new(|arguments: Option<JsonObject>| {
            Box::pin(async move {
                let arguments = arguments.unwrap_or_default();
                let a = arguments.get("a").and_then(|v| v.as_i64()).unwrap_or(0);
                let b = arguments.get("b").and_then(|v| v.as_i64()).unwrap_or(0);
                Ok(CallToolResult::success(vec![ContentBlock::text(
                    (a + b).to_string(),
                )]))
            })
        })
    }

    fn error_handler() -> ToolHandler {
        Arc::new(|_arguments: Option<JsonObject>| {
            Box::pin(async move { Ok(CallToolResult::error(vec![ContentBlock::text("boom")])) })
        })
    }

    fn text_of(result: &CallToolResult) -> String {
        result
            .content
            .iter()
            .find_map(|block| match block {
                ContentBlock::Text(text) => Some(text.text.clone()),
                _ => None,
            })
            .unwrap_or_default()
    }

    fn arguments(object: serde_json::Value) -> JsonObject {
        object.as_object().cloned().unwrap_or_default()
    }

    #[test]
    fn registry_register_replace_unregister() {
        let server = ToolServer::new("test-server", "0.1.0", None);
        assert!(server.list_tools().is_empty());

        server
            .register(
                "add",
                "Add two integers",
                json!({"type": "object"}),
                add_handler(),
            )
            .unwrap();
        server
            .register(
                "sub",
                "Subtract two integers",
                json!({"type": "object"}),
                add_handler(),
            )
            .unwrap();
        // Same-name registration replaces silently.
        server
            .register(
                "add",
                "Add two integers (v2)",
                json!({"type": "object"}),
                add_handler(),
            )
            .unwrap();

        let mut tools = server.list_tools();
        tools.sort();
        assert_eq!(tools, vec!["add", "sub"]);

        assert!(server.unregister("add"));
        assert!(!server.unregister("add"));
        assert_eq!(server.list_tools(), vec!["sub"]);
    }

    #[test]
    fn registry_rejects_non_object_schema() {
        let server = ToolServer::new("test-server", "0.1.0", None);
        assert!(
            server
                .register("bad", "Bad schema", json!(42), add_handler())
                .is_err()
        );
        assert!(server.list_tools().is_empty());
    }

    async fn duplex_client_roundtrip(server: ToolServer, expected_text: &str) {
        let (server_r, client_w) = tokio::io::duplex(4096);
        let (client_r, server_w) = tokio::io::duplex(4096);

        let inner = server.inner.clone();
        let server_task = tokio::spawn(async move {
            let service = FabricatioService { server: inner };
            let running = service
                .serve((server_r, server_w))
                .await
                .expect("server init");
            running.waiting().await.expect("server exit");
        });

        let running = ().into_dyn().serve((client_r, client_w)).await.expect("client init");
        let tools = running.list_tools(None).await.expect("list_tools");
        assert_eq!(tools.tools.len(), 1);
        assert_eq!(tools.tools[0].name, "add");
        assert_eq!(
            tools.tools[0].input_schema.get("type"),
            Some(&json!("object"))
        );

        let result = running
            .call_tool(
                CallToolRequestParams::new("add")
                    .with_arguments(arguments(json!({"a": 2, "b": 3}))),
            )
            .await
            .expect("call_tool");
        assert_eq!(text_of(&result), expected_text);

        drop(running);
        server_task.await.expect("server task");
    }

    #[tokio::test]
    async fn duplex_roundtrip_success() {
        let server = ToolServer::new("test-server", "0.1.0", Some("test instructions".into()));
        server
            .register(
                "add",
                "Add two integers",
                json!({"type": "object"}),
                add_handler(),
            )
            .unwrap();
        duplex_client_roundtrip(server, "5").await;
    }

    #[tokio::test]
    async fn duplex_roundtrip_error_result() {
        let server = ToolServer::new("test-server", "0.1.0", None);
        server
            .register(
                "add",
                "Add two integers",
                json!({"type": "object"}),
                error_handler(),
            )
            .unwrap();
        let (server_r, client_w) = tokio::io::duplex(4096);
        let (client_r, server_w) = tokio::io::duplex(4096);

        let inner = server.inner.clone();
        let server_task = tokio::spawn(async move {
            let service = FabricatioService { server: inner };
            let running = service
                .serve((server_r, server_w))
                .await
                .expect("server init");
            running.waiting().await.expect("server exit");
        });

        let running = ().into_dyn().serve((client_r, client_w)).await.expect("client init");
        let result = running
            .call_tool(CallToolRequestParams::new("add").with_arguments(arguments(json!({"a": 1}))))
            .await
            .expect("call_tool");
        assert_eq!(result.is_error, Some(true));
        assert_eq!(text_of(&result), "boom");

        drop(running);
        server_task.await.expect("server task");
    }

    #[tokio::test]
    async fn http_roundtrip() {
        let server = ToolServer::new("test-server", "0.1.0", Some("test instructions".into()));
        server
            .register(
                "add",
                "Add two integers",
                json!({"type": "object"}),
                add_handler(),
            )
            .unwrap();

        let url = server.serve_http("127.0.0.1", 0).await.expect("bind");
        assert!(url.starts_with("http://127.0.0.1:"));
        assert_eq!(server.url().as_deref(), Some(url.as_str()));

        let running =
            ().into_dyn()
                .serve(StreamableHttpClientTransport::from_uri(url.clone()))
                .await
                .expect("client init");
        let tools = running.list_tools(None).await.expect("list_tools");
        assert_eq!(tools.tools.len(), 1);
        assert_eq!(tools.tools[0].name, "add");

        let result = running
            .call_tool(
                CallToolRequestParams::new("add")
                    .with_arguments(arguments(json!({"a": 10, "b": 32}))),
            )
            .await
            .expect("call_tool");
        assert_eq!(text_of(&result), "42");

        drop(running);
        server.shutdown().await;
        assert_eq!(server.url(), None);
    }
}
