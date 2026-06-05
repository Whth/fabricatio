# `fabricatio-team`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-team)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-team)](https://pypi.org/project/fabricatio-team/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-team/week)](https://pepy.tech/projects/fabricatio-team)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-team)](https://pepy.tech/projects/fabricatio-team)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Team coordination for Fabricatio agents. Provides a `Team` container for assembling agent rosters,
a `Cooperate` mixin that gives individual roles awareness of their teammates, and optional integration
with `fabricatio-digest` for task planning across a team.

Requires Python 3.12+.

## Installation

```bash
pip install fabricatio[team]
# or
uv pip install fabricatio[team]
```

## Key Components

### `Team`

Dataclass that manages a set of `RoleName` members. Build a team, add or remove members, then call
`inform()` to notify every `Cooperate`-capable member of the full roster and `dispatch()` to activate them all.

```python
from fabricatio_core import Role
from fabricatio_team.models.team import Team
from fabricatio_team.capabilities.team import Cooperate

class Analyst(Cooperate):
    ...

class Reviewer(Cooperate):
    ...

alice = Analyst(name="alice")
bob = Reviewer(name="bob")

team = Team()
team.join(alice).join(bob)
team.inform()
team.dispatch()
```

| Method | Description |
|---|---|
| `join(teammate)` | Add a `Role` or `RoleName` to the team. Raises `ValueError` on duplicates. |
| `resign(teammate)` | Remove a `Role` or `RoleName`. Raises `ValueError` if not present. |
| `inform()` | Push the member roster into every `Cooperate`-enabled member's `team_roster`. |
| `dispatch()` | Call `dispatch()` on every member (resolves their config and activates them). |

### `Cooperate`

Mixin class (extends `ScopedConfig`, `ABC`) that gives a `Role` team-awareness. Inherit from it
alongside a base `Role` to let the role track teammates, look them up by name, and collect their
event acceptors for workflow routing.

```python
from fabricatio_core import Role
from fabricatio_team.capabilities.team import Cooperate

class Planner(Role, Cooperate):
    async def plan(self, task: str):
        for mate in self.team_members:
            info = mate.bio
            # delegate subtasks based on bio
        ...
```

| Attribute / Method | Description |
|---|---|
| `team_roster: Set[RoleName] \| None` | Full set of team member names. Set by `inform()` or `update_team_roster()`. |
| `other_member_roster: Set[RoleName] \| None` | Team roster excluding self. Populated when `myself` is passed to `update_team_roster`. |
| `team_members` (property) | Resolved `List[Role]` — looks up every name in `team_roster` via the role registry. |
| `update_team_roster(members, myself=None)` | Replace the roster from an iterable of `RoleName`; optionally sets `other_member_roster`. |
| `update_team_roster_with_roles(roles)` | Convenience — extracts names from `Role` instances and calls `update_team_roster`. |
| `consult_team_member(name)` | Look up a single teammate by name. Returns `Role` or `None` with a warning. |
| `gather_accept_events()` | Collects `accept_events` from every teammate for event-driven routing. |

### `CooperativeDigest`

Optional mixin (requires `fabricatio-digest`) that combines `Cooperate` with the `Digest` task-planning capability.
When installed, exposes `cooperative_digest(requirement, with_self=True)` — it delegates to `Digest.digest`,
automatically passing the team roster as context so the generated task list accounts for all available members.

```bash
pip install fabricatio[team,digest]
```

```python
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_team.capabilities.digest import CooperativeDigest

class TeamPlanner(CooperativeDigest, Digest):
    ...

planner = TeamPlanner()
tasks = await planner.cooperative_digest("Build the authentication module")
```

### Configuration

`TeamConfig` is an empty frozen dataclass registered under the `"team"` key in Fabricatio's configuration
system. Extend it to add team-level settings (e.g. max members, timeout).

```python
from fabricatio_team.config import team_config
```

## Package Structure

```
fabricatio-team/
├── python/fabricatio_team/
│   ├── models/
│   │   └── team.py            - Team dataclass
│   ├── capabilities/
│   │   ├── team.py            - Cooperate mixin
│   │   └── digest.py          - CooperativeDigest (optional)
│   ├── actions/               - Action stubs (extend here)
│   ├── workflows/             - Workflow stubs (extend here)
│   ├── config.py              - TeamConfig
│   └── __init__.py
└── pyproject.toml
```

## Dependencies

- `fabricatio-core` — `Role`, `RoleName`, `ScopedConfig`, configuration system, event routing
- `fabricatio-digest` (optional) — enables `CooperativeDigest` for team-aware task planning

## License

MIT — see [LICENSE](../../LICENSE)
