# TODO

- [ ] Finalize the webui.
    - [ ] Chat interface + API client + WebSocket/SSE streaming
    - [ ] Config panel + agent status dashboard
    - [x] Error handling + loading states + UX polish
    - [ ] Wire Python execution bridge — hook `bridge.py` into Rust `/api/execute` via PyO3 so workflows actually run (
      currently just enqueues)
    - [ ] Workflow save/load — persist workflows as JSON (file or SQLite), load into editor
    - [ ] Clean up scaffolding — remove TheWelcome, HelloWorld, counter.ts, unused AboutView, default Vue assets
    - [ ] Undo/Redo — command pattern on workflow store (add/remove/move node, add/remove edge)
    - [ ] Dark/Light theme toggle — CSS variables + Pinia persistence
    - [ ] Real-time LLM token streaming — surface `WsMessage::LlmToken` in UI for streaming text output during
      generation
    - [ ] Workflow import/export — download as JSON, import from file, share workflows
    - [ ] Responsive layout — collapsible sidebars on mobile, resizable panels
