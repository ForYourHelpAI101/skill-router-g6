---
name: skill-router-g6
description: Self-learning skill router for AI agents. 6-stage pipeline: RAG history, keyword match, BM25 body retrieval, Thompson sampling, competence handbook, DPP diversity. Anti-hallucination gate.
version: 6.2
---

# Skill Router G6

Self-learning skill router for AI agents. Model-agnostic MCP server.

## Tools

| Tool | Description |
|------|-------------|
| `route_skills` | Route a query to the best 5 skills |
| `record_outcome` | Feed back success/failure for self-learning |
| `router_stats` | View handbook + posterior stats |
| `router_history` | Last 10 routing decisions |

## Architecture

6-stage linear pipeline (~120ms):
```
Query → [RAG History] + [Keyword Match] + [BM25 Body Retrieval]
            ↓                          ↓
     [Thompson Boost]  ←  [Handbook Competence]
            ↓
     [DPP-Greedy Diversity] → Final top-5
     ↓
  FINAL GATE: validate all against handbook
```

Self-learning: `record_outcome()` updates Beta posteriors per skill + handbook competence from task outcomes.

## Setup

See [AGENT_INTEGRATION.md](AGENT_INTEGRATION.md) for instructions across all agents.
