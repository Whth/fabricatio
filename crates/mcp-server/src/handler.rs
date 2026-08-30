use std::sync::Arc;

use rmcp::{
    ErrorData, ServerHandler,
    handler::server::tool::ToolCallContext,
    model::{
        CallToolRequestParams, CallToolResponse, InitializeRequestParams, InitializeResult,
        ListToolsResult, PaginatedRequestParams, ProtocolVersion, ServerInfo,
    },
    service::{RequestContext, RoleServer},
};

use crate::ServerInner;

/// Server handler delegating every tool operation to the shared tool router.
///
/// A single [`ToolServer`][crate::ToolServer] may serve many connections
/// (stdio process, HTTP sessions); each connection gets its own
/// `FabricatioService` instance backed by the same `Arc<ServerInner>`, so
/// tools registered at runtime are visible to every session immediately.
pub struct FabricatioService {
    pub(crate) server: Arc<ServerInner>,
}

impl ServerHandler for FabricatioService {
    async fn initialize(
        &self,
        request: InitializeRequestParams,
        context: RequestContext<RoleServer>,
    ) -> Result<InitializeResult, ErrorData> {
        // Bind the router's notifier to this session's peer so later
        // register/unregister calls emit `notifications/tools/list_changed`.
        // The router holds a single notifier slot: with multiple HTTP
        // sessions the most recently initialized session receives the
        // notifications (stdio has exactly one session).
        if let Ok(mut router) = self.server.router.write() {
            router.bind_peer_notifier(&context.peer);
        }
        context.peer.set_peer_info(request.clone());
        let mut info = self.get_info();
        // Mirror rmcp's private negotiation: echo the client-requested
        // version when supported, otherwise keep the server default.
        if self
            .supported_protocol_versions()
            .contains(&request.protocol_version)
        {
            info.protocol_version = request.protocol_version;
        }
        Ok(info)
    }

    async fn call_tool(
        &self,
        request: CallToolRequestParams,
        context: RequestContext<RoleServer>,
    ) -> Result<CallToolResponse, ErrorData> {
        let tcc = ToolCallContext::new(self, request, context);
        // Resolve the route under a brief read lock, then invoke the cloned
        // route outside the lock: the guard is not `Send` and must not span
        // the await. Cloning is cheap — the handler itself is an `Arc`.
        let route = {
            let router = self.server.router.read().unwrap_or_else(|e| e.into_inner());
            router.map.get(tcc.name()).cloned()
        };
        match route {
            Some(route) => (route.call)(tcc).await,
            None => Err(ErrorData::invalid_params("tool not found", None)),
        }
    }

    async fn list_tools(
        &self,
        _request: Option<PaginatedRequestParams>,
        context: RequestContext<RoleServer>,
    ) -> Result<ListToolsResult, ErrorData> {
        let supports_cache_hints = context
            .protocol_version()
            .is_some_and(|version| version >= ProtocolVersion::V_2026_07_28);
        Ok(ListToolsResult {
            tools: self
                .server
                .router
                .read()
                .unwrap_or_else(|e| e.into_inner())
                .list_all(),
            ttl_ms: supports_cache_hints.then_some(0),
            cache_scope: supports_cache_hints.then_some(rmcp::model::CacheScope::Public),
            ..Default::default()
        })
    }

    fn get_tool(&self, name: &str) -> Option<rmcp::model::Tool> {
        self.server
            .router
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .get(name)
            .cloned()
    }

    fn get_info(&self) -> ServerInfo {
        self.server.info.clone()
    }
}
