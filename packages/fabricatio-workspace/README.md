# `fabricatio-workspace`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-workspace)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-workspace)](https://pypi.org/project/fabricatio-workspace)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-workspace/week)](https://pepy.tech/projects/fabricatio-workspace)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-workspace)](https://pepy.tech/projects/fabricatio-workspace)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Git worktree management for Fabricatio, backed by Rust via PyO3 bindings.

---

## Installation

```bash
pip install fabricatio[workspace]
# or: pip install fabricatio-workspace
```

## Overview

`fabricatio-workspace` provides high-performance Git worktree operations — fork, commit, and prune — implemented in Rust and exposed to Python through PyO3 bindings. It is designed for agent-driven workflows that need to create isolated working branches, commit changes programmatically, and clean up stale worktrees.

The Rust layer uses `git2` (libgit2) directly, avoiding subprocess overhead and providing structured error handling for every operation.

## Key API

All core functions live in `fabricatio_workspace.rust`. A thin Python wrapper is available via `fabricatio_workspace.capabilities.workspace.Workspace`.

### `fork(repo_path, to, branch_name, base_branch=None, exist_ok=False) -> Path`

Creates a new Git worktree linked to a branch. Creates the branch if it does not exist (optionally from `base_branch`). Returns the absolute path to the new worktree.

- `exist_ok=True`: returns the existing worktree path instead of raising if the branch is already checked out.
- On failure, partial directories are automatically cleaned up.

### `commit(worktree_path, msg, files=None) -> str`

Stages and commits changes in a worktree. Returns the hex OID of the new commit.

- `files`: optional list of relative paths to stage. If `None` or empty, all modified tracked files are staged.
- Author/committer identity is read from the worktree's Git config.

### `prune(repo_path) -> int`

Prunes all stale worktree metadata from the repository. Returns the number of worktrees pruned. After pruning, branches previously locked by stale worktrees become available for checkout.

### `Workspace` (Python wrapper)

```python
from fabricatio_workspace.capabilities.workspace import Workspace

ws = Workspace()
path = ws.fork("/path/to/repo", "/tmp/feature-42", "feature/42", base_branch="main")
oid = ws.commit(path, "Add new feature", files=["src/module.py"])
```

### `WorkspaceConfig` / `workspace_config`

Loaded from the Fabricatio config system (`fabricatio_core.CONFIG.load("workspace", ...)`). An extensible frozen dataclass for workspace-level configuration.

## Usage Example

```python
from pathlib import Path
from fabricatio_workspace.rust import fork, commit, prune

repo = Path("/home/user/my-project")

# Fork a new worktree from main
wt = fork(repo, Path("/tmp/worktrees/task-1"), "task/do-thing", base_branch="main")

# ... make changes to files in wt ...

# Commit all modified files
commit_oid = commit(wt, "Complete the task", files=None)
print(f"Committed: {commit_oid}")

# Clean up stale worktrees
removed = prune(repo)
print(f"Pruned {removed} stale worktree(s)")
```

## Dependencies

- `fabricatio-core` — configuration loading and core interfaces
- `git2` (vendored, via `libgit2`) — all Git operations run in-process through Rust, no `git` CLI required

## License

This project is licensed under the MIT License.
