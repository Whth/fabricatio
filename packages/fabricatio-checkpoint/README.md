# `fabricatio-checkpoint`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-checkpoint)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-checkpoint)](https://pypi.org/project/fabricatio-checkpoint/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-checkpoint/week)](https://pepy.tech/projects/fabricatio-checkpoint)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-checkpoint)](https://pepy.tech/projects/fabricatio-checkpoint)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Worktree checkpointing via shadow Git repositories for fabricatio workflows. Save, diff, rollback individual files, or reset entire directories — without interfering with any existing Git repository.

## Installation

```bash
pip install fabricatio[checkpoint]
```

For a full installation with all fabricatio components:

```bash
pip install fabricatio[full]
```

## Overview

`fabricatio-checkpoint` maintains a **bare Git shadow repository** for each tracked worktree directory. It stages and commits file changes behind the scenes, enabling:

- **Checkpoints** — save worktree state at any point with a message
- **Selective rollback** — restore individual files to a previous commit without touching others
- **Full reset** — revert the entire worktree to a prior checkpoint
- **Diffs** — retrieve file-level changes between any commit and the current state
- **Status** — list modified, added, or deleted files since the last checkpoint

The shadow repositories live under `~/.fabricatio-checkpoint/` by default and never touch any existing `.git` directory.

## Key Types

### `CheckpointService`

Manages the lifecycle of shadow repositories. Created once per process via the singleton helper.

| Method | Description |
|---|---|
| `get_store(worktree_dir)` | Returns the `CheckPointStore` for a directory (creates on first access) |
| `workspaces()` | Lists all tracked worktree directories |
| `prune_invalid()` | Removes stores whose worktrees no longer exist on disk |

```python
from fabricatio_checkpoint.inited_service import get_checkpoint_service

svc = get_checkpoint_service()
store = svc.get_store("/path/to/project")
```

### `CheckPointStore`

A shadow repository bound to one worktree directory. Backed by a bare Git repo (Rust implementation via PyO3).

| Method | Description |
|---|---|
| `save(commit_msg=None)` | Stage all changes and commit. Returns the commit OID. |
| `head()` | Returns the OID of the current HEAD commit. |
| `commits()` | Returns all commit OIDs in chronological order. |
| `reset(commit_id)` | Restore the entire worktree to a given commit. |
| `rollback(commit_id, file_path)` | Restore a single file from a commit. |
| `get_file_diff(commit_id, file_path)` | Returns the unified diff for a file at a commit. |
| `get_status()` | Lists changed files since HEAD (staged + unstaged). |

```python
store = svc.get_store("/path/to/project")

cid = store.save("snapshot before refactor")
store.rollback(cid, "src/main.py")
store.reset(cid)
print(store.get_file_diff(cid, "src/main.py"))
```

### `Checkpoint` (Capability Mixin)

A `UseLLM`-compatible mixin for use within fabricatio agent roles.

| Method | Description |
|---|---|
| `save_checkpoint(msg)` | Save current state with a message |
| `rollback(commit_id, file_path)` | Restore one file to a previous commit |
| `reset_to_checkpoint(commit_id)` | Reset entire worktree to a commit |
| `get_file_diff(commit_id, file_path)` | Diff one file against a commit |
| `mount_checkpoint_store(store)` | Attach a specific store (defaults to worktree_dir) |
| `unmount_checkpoint_store()` | Detach the current store |

```python
from fabricatio_checkpoint.capabilities.checkpoint import Checkpoint

class MyAgent(Checkpoint, SomeLLMRole):
    worktree_dir = Path("/path/to/project")

agent = MyAgent().mount_checkpoint_store()
cid = agent.save_checkpoint("before editing")
agent.rollback(cid, "config.toml")
```

### `prune_stores(stores_root)`

Free function: deletes shadow repositories under `stores_root` whose worktree directories no longer exist.

```python
from fabricatio_checkpoint.rust import prune_stores

prune_stores(Path.home() / ".fabricatio-checkpoint")
```

## CLI

The package ships a `ckpt` command (requires `pip install fabricatio-checkpoint[cli]`):

```bash
ckpt --workspace /path/to/project save "checkpoint message"
ckpt --workspace /path/to/project reset <commit_id>
ckpt --workspace /path/to/project diff
ckpt --workspace /path/to/project ls
ckpt workspaces
```

## Configuration

Configuration is loaded through `fabricatio-core`'s config system under the `"checkpoint"` key:

- `checkpoint_dir` — directory for shadow repositories (default: `~/.fabricatio-checkpoint`)
- `cache_size` — max cached `CheckPointStore` instances in memory (default: `100`)

```python
from fabricatio_checkpoint.config import checkpoint_config

checkpoint_config.checkpoint_dir = Path("/custom/checkpoint/path")
checkpoint_config.cache_size = 50
```

## Dependencies

- `fabricatio-core` — core interfaces and config system

No additional Python dependencies required for basic use. The optional `[cli]` extra adds `typer`.

## License

MIT — see [LICENSE](../../LICENSE)
