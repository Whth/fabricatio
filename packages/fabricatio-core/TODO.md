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
- [ ] Dummy/mock LLM responses must not enter the shared completion cache.
    - [ ] `llm_no_cache = True` (what `LLMTestRole` sets) bypasses the cache read only:
          `Router::invoke_fresh` still writes the response back (`crates/thryd/src/route/mod.rs`),
          so a dummy's canned text lands in `.cache.db.heed` under `blake3(request.message)`
          (`crates/thryd/src/route/tag.rs`) — a key a live deployment also uses for the same
          prompt bytes.
    - [ ] Roles that are not `LLMTestRole` (e.g. the plain `Role.with_bio(...)` that
          fabricatio-novel's workflow tests subscribe) resolve `llm_no_cache` to
          `CONFIG.llm.no_cache` (False), so they read and write the shared store; embeddings
          default to `embedding_no_cache = False` (`models/generic.py`) even under a test role.
    - [ ] Decide: (a) make `no_cache=True` skip the write-back too — note the retry path in
          `capabilities/usages.py` deliberately uses that write-back to overwrite a stale entry;
          (b) keep core as-is and set `llm_no_cache=True` wherever the dummy is used;
          (c) put the deployment in the cache key so dummy and live entries can never collide.
