# `fabricatio-memory`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-memory)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-memory)](https://pypi.org/project/fabricatio-memory/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-memory/week)](https://pepy.tech/projects/fabricatio-memory)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-memory)](https://pepy.tech/projects/fabricatio-memory)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Memory management for Fabricatio agents — persistent, searchable long-term memory backed by a Tantivy full-text index in Rust.

---

## Installation

```bash
pip install fabricatio[memory]
# or
uv pip install fabricatio[memory]
```

For a full installation including all optional packages:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## Overview

`fabricatio-memory` provides a persistent memory system for LLM agents. It combines a Rust-backed Tantivy search engine with Python-level agent capabilities to record, search, and recall information across sessions.

Memories are stored in named **stores** (independent Tantivy indexes). Each memory carries content, an importance score, tags, and is tracked for access frequency and recency — enabling relevance-boosted retrieval.

The Python layer wraps recording and recall through LLM integration: raw text is structured into a `Note` by the agent's LLM before storage, and recall queries return LLM-summarized results from the top matching memories.

## Architecture

```
Python (capabilities)          Rust (storage engine)
┌─────────────────────┐       ┌──────────────────────┐
│ Remember            │──▶    │ MemoryStore          │
│  .record(raw)       │       │  .add_memory()       │
│  .recall(query)     │       │  .search_memories()  │
│ SelectiveRemember   │       │  .get_memory()       │
│  .sremember(…)      │       │  .update_memory()    │
└─────────────────────┘       │  .stats()            │
                              └──────────────────────┘
                                        │
                              ┌──────────────────────┐
                              │ MemoryService        │
                              │  .get_store(name)    │
                              │  .list_stores()      │
                              └──────────────────────┘
```

## Key APIs

### Rust backend (`fabricatio_memory.rust`)

| Type | Description |
|------|-------------|
| `Memory` | A single memory entry: `uuid`, `content`, `timestamp`, `importance` (0–100), `tags`, `access_count`, `last_accessed`. |
| `MemoryService(root, buffer_size, cache_size)` | Manages named stores. Creates/opens Tantivy indexes under `root`. |
| `MemoryStore` | CRUD and search on one index. |
| `MemoryStats` | Aggregated metrics: `total_memories`, `avg_importance`, `avg_access_count`, `avg_age_days`. |

**`MemoryStore` methods:**

| Method | Description |
|--------|-------------|
| `add_memory(content, importance, tags)` | Store a new memory; returns its UUID. |
| `get_memory(uuid)` | Retrieve by ID (updates access count). |
| `update_memory(uuid, content?, importance?, tags?)` | Update fields; returns `True` if found. |
| `delete_memory(uuid)` | Delete by ID. |
| `search_memories(query, top_k, boost_recent)` | Full-text search, optionally boosting recent entries. |
| `search_by_tags(tags, top_k)` | Filter by tags (OR semantics). |
| `get_memories_by_importance(min, top_k)` | Filter by minimum importance. |
| `get_recent_memories(days, top_k)` | Memories from the last N days. |
| `get_frequently_accessed(top_k)` | Most-accessed memories first. |
| `count_memories()` | Total stored documents. |
| `stats()` | Aggregated `MemoryStats`. |
| `write()` | Flush pending writes to disk. |

All mutation methods accept an optional `write=False` parameter; when `False`, changes are buffered for performance. Call `write()` to commit.

### Python capabilities (`fabricatio_memory.capabilities`)

| Class | Description |
|-------|-------------|
| `Remember` | Mixin providing `record()` and `recall()`. Uses the agent's LLM to structure raw text into a `Note` (content + importance + tags), then stores it. Recall searches the store and summarizes results via LLM. |
| `SelectiveRemember` | Extends `Remember` with `sremember()` — conditionally records only when a judgment (powered by `fabricatio-judge`) deems the information worth keeping. |

### Models (`fabricatio_memory.models`)

| Class | Fields |
|-------|--------|
| `Note` | `content: str`, `importance: int` (0–100), `tags: List[str]`. Pydantic model; LLM output target for `record()`. |

### Configuration (`fabricatio_memory.config`)

`MemoryConfig` controls template paths, store root directory (`~/.fabricatio-memory` by default), writer buffer size (50 MB default), and index cache size (10 stores).

### Service singleton (`fabricatio_memory.inited_memory_service`)

`get_memory_service()` returns a lazily-initialized `MemoryService` using the global `MemoryConfig`.

## Usage

### Direct store operations

```python
from fabricatio_memory.rust import MemoryService

service = MemoryService("/path/to/store_root")
store = service.get_store("my_agent")

# Store a memory
mem_id = store.add_memory("User prefers dark mode", importance=70, tags=["preferences", "ui"])

# Search
results = store.search_memories("dark mode", top_k=5, boost_recent=True)
for mem in results:
    print(f"{mem.uuid}: {mem.content} (importance={mem.importance})")

# Stats
stats = store.stats()
print(stats.display())
# total: 42, avg importance: 55.3, avg access: 3.1, avg age: 12.4d

# Commit buffered writes
store.write()
```

### Agent capability (LLM-integrated)

```python
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_memory.inited_memory_service import get_memory_service

class MyAgent(Remember, SomeBaseAgent):
    ...

agent = MyAgent(memory_store_name="agent_memories")
agent.mount_memory_store()

# Record — LLM extracts structured Note from raw text
note = await agent.record("The user said their name is Alice and they work at Acme Corp.")
# note.content = "User name is Alice, works at Acme Corp."
# note.importance = 60
# note.tags = ["user_info", "employment"]

# Recall — semantic search + LLM summarization
summary = await agent.recall("What do we know about Alice?")
# summary = "Alice works at Acme Corp. She prefers dark mode."
```

### Selective memory

```python
from fabricatio_memory.capabilities.selective_remember import SelectiveRemember

class MyAgent(SelectiveRemember, SomeBaseAgent):
    ...

# Only record if the agent judges it's worth remembering
note = await agent.sremember(
    prerequisite="Only remember if this contains personal user information",
    raw="The weather is sunny today."
)
# note is None — weather isn't personal info
```

## Dependencies

- `fabricatio-core` — core interfaces, configuration, template management
- Optional: `fabricatio-judge` — required by `SelectiveRemember` for conditional recording

## License

MIT — see [LICENSE](../../LICENSE)
