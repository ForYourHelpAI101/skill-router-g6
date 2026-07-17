# Skill Router G6

Self-learning skill router for AI agents. Model-agnostic MCP server. Two modes: harness injection (Ralph Loop) or direct MCP tool calls.

## Quick Start

### Harness Mode (recommended — zero model compliance needed)
Wire into Hermes `config.yaml`:
```yaml
hooks:
  pre_llm_call:
    - command: "path/to/hermes_hook.py"
```
The harness calls `route_skills`, injects `🎯 Router:` into context. Model just displays it.

### MCP Mode (all other agents)
```bash
claude mcp add skill-router --command python --args "path/to/mcp_server.py"
```

Instruction file for MCP mode:
```markdown
## Router (MANDATORY)
Before replying to any substantive message:
1. Call mcp__skill_router__route_skills with the user's query.
2. Show: 🎯 Router: primary-skill (also: alt-1, alt-2, alt-3, alt-4)

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
