# TODO

- [ ] Add api support.
    - [ ] Define API types + REST route handlers + wire into axum server
    - [ ] Add CORS/error middleware + Python binding for server config
    - [ ] Integration tests + API docs
- [ ] Run as mcp server.
    - [ ] Feature flag + `McpServer` struct + tool registry + `tools/list`
    - [ ] stdio + HTTP transports + `tools/call` dispatch
    - [ ] Register Fabricatio tools as MCP tools + Python binding + tests
- [ ] Add Plugin system.
    - [ ] Plugin protocol + registry + lifecycle (load/unload)
    - [ ] Hook points in core lifecycle + entry-point discovery
    - [ ] Plugin config support + validation + tests
