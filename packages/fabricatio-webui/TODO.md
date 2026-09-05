# TODO

Re-verified 2026-09-02 against source and live runs.

- [ ] Finalize the webui.
    - [ ] Chat interface + API client + WebSocket/SSE streaming
    - [ ] Config panel + agent status dashboard
    - [x] Error handling + loading states + UX polish
    - [x] Wire Python execution bridge — `/api/execute` → PyO3 `submit_fn` →
      `WorkflowWorker` → namespace dispatch → Action graph; verified live
      end-to-end (Hello Fabricatio returns the expected summary)
    - [x] Workflow save/load — boards are CRUD-managed via
      `GET|POST /api/workflows` and `GET|DELETE /api/workflows/{id}` and
      persisted server-side
    - [x] Clean up scaffolding — TheWelcome, HelloWorld, counter.ts,
      AboutView, and default Vue assets are gone
    - [ ] Undo/Redo — command pattern on workflow store (add/remove/move node, add/remove edge)
    - [x] Dark/Light theme toggle — CSS variables + Pinia persistence
    - [ ] Real-time LLM token streaming — surface `WsMessage::LlmToken` in UI
      for streaming text output during generation (receive path implemented
      end-to-end; nothing emits token events yet)
    - [x] Workflow import/export — download as JSON, import from file
    - [x] Selectable export — the codegen dialog picks a scope (whole role
      or a single workflow) and a format (script zip, installable CLI
      package with `[project.scripts]`, typed library package, PyPI-ready
      skeleton with LICENSE/tests/ruff/release workflow); every generated
      file is previewed in tabs before export
    - [ ] Responsive layout — collapsible sidebars on mobile, resizable panels
    - [x] Localization (i18n) — vue-i18n with `en`/`zh` message catalogs
      (`src/locales/`); locale switcher in Settings → Appearance persists the
      choice alongside the theme; canvas hints, dialogs, notifications,
      settings, and console are all catalog-driven
