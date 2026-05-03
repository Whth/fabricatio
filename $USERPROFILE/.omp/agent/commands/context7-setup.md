---
description: Set up Context7 MCP server in oh-my-pi
---

## Context7 MCP Setup

Context7 provides up-to-date library documentation for AI coding agents.

### Server Details

- **Name**: `context7`
- **Type**: `http`
- **URL**: `https://mcp.context7.com/mcp`
- **Auth**: API key via `CONTEXT7_API_KEY` header

### Configuration

Add to `~/.omp/agent/mcp.json`:

```json
{
  "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "CONTEXT7_API_KEY"
      }
    }
  }
}
```

### Getting an API Key

1. Sign up at https://context7.com
2. Get your API key from the dashboard
3. Set `CONTEXT7_API_KEY` in your shell environment or `.env`

### Verify

```bash
# Reload MCP servers in oh-my-pi
/mcp reload

# List servers to confirm
/mcp list

# Test context7
/mcp test context7
```

### Available Tools (once connected)

- `resolve-library-id` - Find Context7 library ID by name
- `query-docs` - Get documentation for a library

### Usage in Prompts

```
How do I set up Next.js middleware? use context7
Show me Supabase auth API for email sign-up. use context7
```
