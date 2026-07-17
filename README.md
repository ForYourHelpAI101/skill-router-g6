# Skill Router G6

Self-learning skill router for AI agents. Model-agnostic MCP server.

## Quick Start

Add to any agent via MCP:
```bash
# Hermes
hermes mcp add skill-router --command python --args "path/to/mcp_server.py"

# Claude Code
claude mcp add skill-router --command python --args "path/to/mcp_server.py"

# Cursor / Windsurf / Codex — edit .mcp.json
```

Add to your agent's instruction file:
```markdown
## Router (MANDATORY)
Before replying to any substantive message (10+ words):
1. Call mcp__skill_router__route_skills with the user's query.
2. Show the top 5 skills: 🎯 Router: a, b, c, d, e

After any task (5+ tool calls):
1. Call mcp__skill_router__record_outcome with: query, skills, success=true/false.
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `route_skills` | Route a query to the best 5 skills |
| `record_outcome` | Feed back success/failure for self-learning |
| `router_stats` | View handbook + posterior stats |
| `router_history` | Last 10 routing decisions |

## Architecture

6-stage pipeline (~120ms):
```
Query → [RAG History] + [Keyword Match] + [BM25 Body Retrieval]
            ↓                          ↓
     [Thompson Boost]  ←  [Handbook Competence]
            ↓
     [DPP-Greedy Diversity] → Final top-5
     ↓
  FINAL GATE: validate all against handbook
```

Anti-hallucination: 5-layer defense. Self-learning: Beta posteriors from task outcomes.

See [AGENT_INTEGRATION.md](AGENT_INTEGRATION.md) for full setup across all agents.
