---
description: Add an MCP server to oh-my-pi
---

## Steps

### 1. Get required configuration

Ask the user for:
- MCP server name
- Server type: `stdio`, `http`, or `sse`
- For stdio: `command` (e.g., `npx`, `node`, path to binary)
- For http/sse: `url` (the server endpoint URL)
- Optional: `args` for stdio, `headers` for http/sse
- Optional: API key or auth config

### 2. Determine config location

- Project-level: `.omp/mcp.json`
- User-level: `~/.omp/agent/mcp.json`

Use user-level unless there's a project-specific reason.

### 3. Create/update the config file

Add to `mcpServers`:

```json
{
  "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
  "mcpServers": {
    "<server-name>": {
      "type": "<stdio|http|sse>",
      "command": "<command>",
      "args": ["<arg1>", "<arg2>"],
      "env": {
        "VAR_NAME": "VAR_NAME"
      }
    }
  }
}
```

For HTTP servers:
```json
{
  "$schema": "...",
  "mcpServers": {
    "<server-name>": {
      "type": "http",
      "url": "https://...",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
```

### 4. Environment variable resolution

In `.omp/mcp.json` and `~/.omp/agent/mcp.json`:
- `"VAR_NAME": "VAR_NAME"` → copy from shell environment
- `"VAR_NAME": "Bearer hardcoded-token"` → literal value
- `"VAR_NAME": "!printf 'Bearer %s' \"$TOKEN\""` → run shell command

### 5. Verify the config

Use `/mcp reload` to rediscover servers.
Use `/mcp list` to see which config file a server came from.
Use `/mcp test <name>` to test a single server.

### 6. Commit (if project-level)
