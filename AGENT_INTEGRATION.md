# Skill Router G6 — Agent Integration Guide

Force-integrate skill routing + self-learning feedback into any AI coding agent. Model-agnostic — works with DeepSeek, Claude, GPT, Gemini, Llama, Qwen, and all others.

Two integration modes:

| Mode | How | Best for |
|------|-----|----------|
| **Harness (Ralph Loop)** | `pre_llm_call` hook injects routing | Hermes — zero model compliance needed |
| **MCP Tool** | Model calls `route_skills` itself | Claude Code, Cursor, Codex, all others |

---

## Mode 1: Harness Injection (Hermes — recommended)

The harness does the routing. The model just displays the result.

### 1. Wire the hook
```yaml
# config.yaml
hooks:
  pre_llm_call:
    - command: "path/to/hermes_hook.py"
```

### 2. Instruction file
```
## Router (HARNESS-INJECTED — do not call route_skills)
The harness injects a 🎯 Router: line before every turn. Display it EXACTLY as provided at the very start of your response.

After any task (5+ tool calls):
1. Call mcp__skill_router__record_outcome with: query, skills, success=true/false.
2. Skip for single-tool operations.
```

This is a **Ralph Loop** — the hook runs outside the model's control. It calls `route_skills`, injects the result as context, and the model cannot skip it. No MCP call, no hallucination, no instruction drift.

---

## Mode 2: MCP Tool (all other agents)

The model calls `route_skills` directly.

### 1. Add MCP server
```bash
# Claude Code
claude mcp add skill-router --command python --args "path/to/mcp_server.py"

# Cursor / Windsurf / Codex — edit .mcp.json
```

### 2. Instruction file
```
## Router (MANDATORY)
Before replying to any substantive message:
1. Call mcp__skill_router__route_skills with the user's query.
2. Show: 🎯 Router: primary-skill (also: alt-1, alt-2, alt-3, alt-4)
3. If the call fails, continue silently.

After any task (5+ tool calls):
1. Call mcp__skill_router__record_outcome with: query, skills, success=true/false.
2. Skip for single-tool operations.
```

---

## Per-Agent Setup

| Agent | Mode | Config | Instruction File | Slot |
|-------|------|--------|-----------------|------|
| Hermes | Harness | `config.yaml` hooks | `~/.hermes/SOUL.md` | Identity #1 |
| Claude Code | MCP | `.mcp.json` | `CLAUDE.md` | Identity #1 |
| Cursor | MCP | `.cursor/mcp.json` | `.cursorrules` | Always |
| Codex | MCP | `~/.codex/mcp.json` | `CODEX.md` | Identity |
| Windsurf | MCP | `.windsurf/mcp.json` | `.windsurfrules` | Always |
| Gemini CLI | MCP | `.gemini/mcp.json` | `GEMINI.md` | Identity |
| Aider | MCP | config | `AIDER.md` | Identity |
| Cline | MCP | VS Code ext | `.clinerules` | Always |
| Continue | MCP | VS Code ext | `.continuerules` | Always |
| Copilot | MCP | N/A | `.github/copilot-instructions.md` | Always |

---

## Architecture

6-stage linear pipeline (120ms avg):

```
Query → [RAG History] + [Keyword Match] + [BM25 Body Retrieval]
            ↓                          ↓
     [Thompson Boost]  ←  [Handbook Competence]
            ↓
     [DPP-Greedy Diversity] → Final top-5 skills
```

Self-learning: `record_outcome()` updates Beta posteriors per skill + handbook competence from task outcomes. Thompson sampling balances exploration/exploitation.

---

## Maintenance

### Bootstrap / Rebuild Handbook
```bash
python -c "
import sys; sys.path.insert(0, 'path/to/skill-router')
from harness_g6 import get_skills, _save_json, CACHE_DIR, HANDBOOK_PATH
CACHE_DIR.mkdir(parents=True, exist_ok=True)
import harness_g6; harness_g6._SKILLS_CACHE = None
skills = get_skills()
handbook = {s.name: {'n':0,'hits':0,'domains':{}} for s in skills}
_save_json(HANDBOOK_PATH, handbook)
print(f'Handbook: {len(handbook)} skills')
"
```

### Nuke Hallucinated History
```bash
echo "[]" > ~/.hermes/.router-cache/routing_history.json
```

### MCP Server Cache
`_SKILLS_CACHE` is process-global. New skills are invisible until the MCP process restarts (new session or `/reset`).

---

## Anti-Hallucination Protections (v6.2)

| Layer | Protection |
|-------|-----------|
| Final gate | `route_g6` drops any skill not in handbook — last line of defense |
| Body matching | `rank_by_body` cross-checks against handbook |
| Keyword patterns | Cross-check against handbook before returning |
| record_outcome | Only updates existing handbook entries — never adds unknowns |
| Handbook | Rebuilt from SKILL.md files with content validation |

---

## ⚠️ Critical Notes

- **Harness mode is preferred** — no model compliance, no instruction drift, zero hallucination risk
- **Instruction format must be model-agnostic** — simple numbered lists work across all models
- **Both `route_skills` AND `record_outcome` must be called** — routing without feedback decays to neutral and never improves
- **Restart after skill additions** — MCP server caches skill list in memory
