---
name: strix-security-scan
description: Autonomous SAST penetration testing, Model Context Protocol (MCP) tool integration, and automated code hardening using Strix, Bandit, and Flake8 within TARA IDE.
---

# Strix Security Scan, MCP Integration & Code Hardening

This skill enables Google Antigravity IDE and TARA agents to run autonomous penetration testing using **Strix** (`usestrix/strix`), Model Context Protocol (MCP) servers, static analysis with Bandit, and linting with Flake8.

## MCP Configuration

Strix connects to Model Context Protocol (MCP) servers via `~/.strix/mcp-servers.json` (or workspace-level `./mcp-servers.json`) and coordinates with Google Antigravity IDE via `~/.gemini/config/mcp_config.json`.

### 1. Strix MCP Servers Config (`~/.strix/mcp-servers.json` or `./mcp-servers.json`)
```json
[
  {
    "name": "local_fs",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
  },
  {
    "name": "github",
    "transport": "http",
    "url": "https://api.githubcopilot.com/mcp/",
    "auth": { "kind": "bearer", "token": "your-github-token-here" },
    "allowed_tools": ["list_issues"]
  }
]
```

### 2. Antigravity IDE MCP Config (`~/.gemini/config/mcp_config.json`)
```json
{
  "mcpServers": {
    "local_fs": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/tanma/TARA"]
    },
    "github": {
      "serverUrl": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer your-github-token-here"
      }
    }
  }
}
```

## Usage & Execution Commands

### Default Execution (Uses all configured MCP servers)
```bash
strix -t ./app-directory
```

### Targeting Specific MCP Servers
```bash
strix --mcp-server github -t ./app-directory
```

### Excluding Specific MCP Servers
```bash
strix --mcp-exclude staging-db -t ./app-directory
```

### Using Custom Workspace Configuration File
```bash
strix --mcp-config ./mcp-servers.json -t ./app-directory
```

### Verifying Connection & Real-Time Dashboard
Look for the startup confirmation in the terminal logs:
```plaintext
MCP: connected 2 servers (14 tools): local_fs, github
```
Open the live execution dashboard:
```bash
strix view
```

### Running via TARA Sandbox & HTTP API
Programmatic execution with MCP arguments:
```bash
python -m app.sandbox.strix_runner
```
Or via HTTP API:
```bash
curl -X POST http://127.0.0.1:8000/api/security/strix-scan \
  -H "Content-Type: application/json" \
  -d '{"mcp_config": "./mcp-servers.json", "mcp_server": "github"}'
```

## How It Works

1. **Triple-Layer Scanning**:
   - **Flake8**: Code quality, syntax errors, and missing imports.
   - **Bandit**: AST analysis for Python security vulnerabilities.
   - **Strix**: Autonomous agentic penetration testing (`strix -n --target ./`), augmented with MCP tools.

2. **Unified Findings**:
   - Results are parsed into the unified `SecurityFindingModel` (`tool`, `severity`, `issue`, `file_path`, `line_number`, `category`, `exploit_poc`).

3. **Automated AI Hardening**:
   - `ChatGoogleGenerativeAI` refactors affected modules and generates clean patches.
   - Diffs are streamed over `/ws/security` into Monaco Editor (`createDiffEditor`).
   - Approved patches can be applied with the "Accept Patch" action (`POST /api/security/apply-patch`).
