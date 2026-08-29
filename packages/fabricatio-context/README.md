# `fabricatio-context`

Branch-based append-only prompt context for prefix-cache hits.

## Overview

LLM providers cache prompts by exact token prefix. Composition code that
interpolates request-specific content into the middle of a prompt invalidates
the cache on every call. This package provides the shared data structure and
capability for building prompts as **stable heads plus cheap branches**:

- [`ContextEntry`] — one frozen block of composed context (`kind`/`title`/`body`).
- [`ContextLog`] — append-only sequence of frozen entries held in an immutable
  tuple: `with_entry`/`with_entries` append purely, `branch` forks history in
  O(1), `clear` hands out a fresh log, `render` joins bodies deterministically.
- [`AssembleContext`] — capability mixin: seed a stable head once, fork a
  per-request branch, append request-specific entries, render byte-stable text.

Identical logs always render byte-identical strings, so a rendered head is a
cache-stable prefix across every request and every retry round.

`fabricatio-novel` uses this pattern for running manuscript context;
`fabricatio-tool` uses it to render execution feedback.

## Usage

```python
from fabricatio_context.capabilities.context import AssembleContext
from fabricatio_context.models.context import ContextEntry, ContextLog


class MyAgent(AssembleContext):
    def context_head(self) -> ContextLog:
        return ContextLog(entries=(
            ContextEntry(kind="rules", title="Rules", body="You SHALL ..."),
        ))


agent = MyAgent()
branch = agent.branch_context()
branch = branch.with_entry(agent.make_entry("request", "Req", "Count the lines"))
prompt_tail = agent.render_context(branch)
```

## License

MIT — see [LICENSE](../../LICENSE)
