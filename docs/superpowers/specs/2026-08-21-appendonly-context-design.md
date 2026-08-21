# Append-only Context for fabricatio-novel — Design

- **Date:** 2026-08-21
- **Status:** Approved design, pending implementation
- **Package:** `packages/fabricatio-novel`
- **Supersedes:** nothing; extends the dataflow documented in `2026-08-21-novel-generation-dataflow.md`

## 1. Problem

The running manuscript context is two opaque strings:

- `ContextBase.prefixed_content: str` — everything composed before an element, injected by
  `iter_prefixed_contexts()` (base.py) as a loop-local accumulator joined with `"\n\n"`.
- `SceneContext.scenes_so_far: str` — the story's earlier scenes, accumulated in
  `StoryCompose.compose_scenes_phase` (capabilities/story.py).

Strings cannot express structure: no entry identity (what composed this block?), no fork point
for alternative continuations, no way to reset a stream without losing history. Every "control"
operation degenerates into string surgery on prompt-critical text.

## 2. Goals

1. Replace both accumulation streams with one structured, append-only log type.
2. Support exactly three control operations: **append**, **branch** (fork history,
   copy-on-write), **clear** (fork fresh; original preserved).
3. Keep rendered prompts byte-identical to today — zero template changes.
4. Serialize natively through the staged workflow's whole-tree JSON snapshots.
5. Clean cutover: the old string fields are deleted, not deprecated.

## 3. Non-goals

- No automatic multi-candidate drafting loop in `compose_scene` (the branching *mechanism*
  lands; driving N candidates per scene is future work unless requested).
- No revision DAG / time-travel queries (event-sourced variant was considered and rejected —
  more machinery than the alternatives-drafting use case needs).
- No changes outside `fabricatio-novel`.

## 4. User decisions (recorded)

| Question | Decision |
|---|---|
| Scope | Unify `prefixed_content` + `scenes_so_far` on one log class |
| Branch semantics | Fork history at any entry; independent appends afterwards |
| Clear semantics | Return a fresh empty log; original log stays intact |
| Rollout | Replace everywhere in one cutover |

## 5. Architecture

New module `python/fabricatio_novel/models/context/log.py`:

```python
class ContextEntry(BaseModel):
    """One immutable block of composed manuscript."""
    model_config = ConfigDict(frozen=True)

    kind: Literal["chapter_header", "scene_content"]
    title: str   # owning element's title
    body: str    # rendered text block


class ContextLog(BaseModel):
    """An append-only sequence of entries with fork/clear support."""
    entries: tuple[ContextEntry, ...] = ()
    forked_at: int = 0   # len(entries) at branch time; snapshot traceability only
```

### Operations

| Operation | Signature | Semantics |
|---|---|---|
| append (pure) | `with_entry(e) -> ContextLog` | New log sharing nothing mutable; old log unchanged |
| append (bulk, pure) | `with_entries(es) -> ContextLog` | Folds `with_entry` over a sequence; used for `prefixed_entries()` contributions |
| append (mutating sugar) | `append(e) -> Self` | Rebinds `entries`; single-owner code only |
| branch | `branch() -> ContextLog` | Shares the entries tuple (O(1)); `forked_at = len(entries)`; both sides append independently |
| clear | `clear() -> ContextLog` | Returns a fresh empty log; receiver untouched |
| render | `render() -> str` | `"\n\n".join(e.body for e in entries if e.body)` — filters falsy bodies exactly like today's conditional joins |

### Invariants

1. **Append-only:** existing entries are frozen (`frozen=True`); mutation attempts raise
   `ValidationError`. No operation edits or reorders history.
2. **Pure pipeline:** all pipeline code uses `with_entry` (pure rebinding). The mutating
   `append` exists for single-owner scripts/tests. This makes cross-object sharing safe:
   a reader holding a log object keeps its exact tuple forever.
3. **Prefix-cache stability preserved:** within a story, every scene receives the same
   `prefix_log` snapshot (constant), while `scenes_log` grows per scene — identical
   structure to today's split, so stable content can still sit between them in prompts.
4. **Byte-identical rendering:** `render()` output equals the legacy `"\n\n".join(...)`
   accumulation for the same blocks, including empty-block filtering.

## 6. Integration

### `models/context/base.py`

- Field: `prefixed_content: str` → `prefix_log: ContextLog = Field(default_factory=ContextLog)`.
- `set_prefixed_content(str)` → `set_prefix_log(log: ContextLog) -> Self`.
- Abstract `render_prefixed_block() -> str` → abstract `prefixed_entries() -> tuple[ContextEntry, ...]`.
- `iter_prefixed_contexts()` becomes fully pure:

  ```python
  seed = self.prefix_log
  header = self.render_prefixed_header()
  if header:
      seed = seed.with_entry(self._header_entry())   # chapter: header entry
  for child in self.iter_child_contexts():
      child.set_prefix_log(seed)
      yield child
      seed = seed.with_entries(child.prefixed_entries())
  ```

  Purity makes repeated tree walks idempotent (the current loop-local string was also
  stateless; the log keeps that property structurally).
- `render_prefixed_header()` stays as-is (chapter renders `# Title\n\n> description`;
  others return `""`) — it remains the body renderer; `_header_entry()` wraps it.

### Per level

| Class | `prefixed_entries()` |
|---|---|
| `NovelContext` | Concatenation of children's entries (contributes nothing itself) |
| `ChapterContext` | `(ContextEntry("chapter_header", self.title, self.render_prefixed_header()),)` |
| `StoryContext` | Concatenation of children's entries |
| `SceneContext` | `(ContextEntry("scene_content", self.title, self.content),)` when content else `()` |

One entry per leaf block — never an aggregated blob. Assembly paths that read prose
(`iter_scene_content`, `iter_story_content`, `iter_chapter_content`, `content` field) are
untouched.

### Story-scoped stream

- `StoryContext.scenes_log: ContextLog = Field(default_factory=ContextLog)` — fresh per story.
- `SceneContext.scenes_so_far: str` → `scenes_log: ContextLog` + `set_scenes_log(log)`.
- `compose_scenes_phase` (capabilities/story.py):

  ```python
  for scene_ctx in ctx.scene_context:
      scene_ctx.set_prefix_log(ctx.prefix_log).set_scenes_log(ctx.scenes_log.branch())
      ...
      ctx.scenes_log = ctx.scenes_log.with_entry(scene_content_entry(scene_ctx))
  ```

  The scene holds a `branch()` snapshot taken before its own composition; the story rebinds
  a new log afterwards. Ordering guarantees the scene's rendered prompt never contains its
  own content.

### Prompt assembly

`_scene_requirement_vars` (capabilities/scene.py):

```python
"prefixed_content": ctx.prefix_log.render(),
"scenes_so_far": ctx.scenes_log.render(),
```

Template variable names and rendered text are unchanged — **no `.hbs` edits, no AppData sync**.

### Branching usage pattern (mechanism, exercised in tests)

```python
base = scene_ctx.prefix_log            # everything before this scene
cand_a = base.branch()                 # draft v1 against identical prefix
cand_b = base.branch()                 # draft v2
# ... pick a winner, append upstream:
ctx.scenes_log = ctx.scenes_log.with_entry(winner_entry)
```

### Serialization

`ContextLog`/`ContextEntry` are plain pydantic models; `PersistentAble` snapshots serialize
them without adapters. `forked_at` records branch points for post-mortem traceability in
staged snapshots.

## 7. Error handling

- Frozen entries: accidental mutation raises instead of corrupting shared history.
- `clear()` cannot destroy the original by construction.
- Empty bodies/blocks filtered identically to legacy joins (no empty sections appear).
- A scene composed against a stale snapshot cannot see later siblings' entries (tuple sharing).

## 8. Testing

New `tests/test_context_log.py`:

1. `with_entry` purity: original log unchanged; order preserved.
2. `branch` isolation both directions (append to fork ≠ parent; append to parent ≠ fork);
   `forked_at` bookkeeping.
3. `clear` returns empty log, original intact.
4. `render()` byte-equality with legacy `"\n\n".join(p for p in (...) if p)` semantics,
   including empty-body filtering.
5. Pydantic round-trip (`model_dump_json` → `model_validate_json`).
6. Frozen-entry mutation raises.

Migrated assertions (same expected strings, new accessors):

- `test_novel.py`: `TestPrefixAccumulation`, hierarchical injection tests,
  `test_prepare_scene_requirement_renders_prefixed_content_after_static_head`,
  scene/story prefix asserts → `.prefix_log.render()` / `.scenes_log.render()`.
- `test_bible.py`: direct `ctx.prefixed_content = ...` setup → `ctx.set_prefix_log(...)`.

These migrations adapt call sites to the renamed contract while pinning identical rendered
output; they do not weaken any assertion.

## 9. Files touched

| File | Change |
|---|---|
| `models/context/log.py` | NEW — `ContextEntry`, `ContextLog` |
| `models/context/base.py` | Field swap, pure walk, `prefixed_entries()` |
| `models/context/{novel,chapter,story,scene}.py` | `prefixed_entries()` impls, `scenes_log` field |
| `capabilities/story.py` | `compose_scenes_phase` log wiring |
| `capabilities/scene.py` | requirement vars render logs |
| `tests/test_context_log.py` | NEW unit suite |
| `tests/test_novel.py`, `tests/test_bible.py` | Accessor migration |
| `README.md` | Context-channel table row for `ContextLog` |

## 10. Verification

1. Red→green: new tests fail before implementation, pass after.
2. Full suite: `.venv/Scripts/python.exe -m pytest packages/fabricatio-novel/python/tests -q`
   (155 baseline + new tests green).
3. `ruff check` + pyright on touched files.
4. Behavioral smoke: the mocked hierarchical compose test exercises
   novel→chapter→story→scene prefix injection end-to-end through the log path.
