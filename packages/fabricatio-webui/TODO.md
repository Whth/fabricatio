# TODO

Re-verified 2026-09-05 against source and live runs.

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
    - [x] Undo/Redo — snapshot history on the workflow store (50 deep,
      branch-discard; Ctrl+Z / Ctrl+Shift+Z and palette entries wired)
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
    - [x] Per-workflow debug run — ▶ button on every role-card workflow chip
      opens the run dialog pre-filled with that workflow's name, namespace,
      and stored init context; Ctrl+Enter inside the workflow editor and the
      toolbar free-form Publish stay separate (verified live end-to-end)
    - [ ] Responsive layout — collapsible sidebars on mobile, resizable panels
    - [x] Localization (i18n) — vue-i18n with `en`/`zh` message catalogs
      (`src/locales/`); locale switcher in Settings → Appearance persists the
      choice alongside the theme; canvas hints, dialogs, notifications,
      settings, and console are all catalog-driven
