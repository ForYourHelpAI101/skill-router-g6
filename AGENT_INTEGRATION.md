# Skill Router G6 — Agent Integration Guide

Force-integrate skill routing + self-learning feedback into any AI coding agent. Model-agnostic — works with DeepSeek, Claude, GPT, Gemini, Llama, Qwen, and all others.

---

## MCP Server Config (stdin/stdout JSON-RPC)

```yaml
command: python  # or full path to python3/python.exe
args:
  - path/to/mcp_server.py
```

### Example: Hermes Agent
```bash
hermes mcp add skill-router --command python --args "path/to/mcp_server.py"
```

---

## Force Embed Per Agent

### The Instruction Text — Model-Agnostic (copy-paste into your instruction file)

```
## Router (MANDATORY)
Before replying to any substantive user message (not a correction or trivial reply):
1. Call mcp__skill_router__route_skills with the user's query.
2. Announce the skill you intend to use — the FIRST result is your pick
3. If the call fails, continue silently. .

After any task (5+ tool calls):
1. Call mcp__skill_router__record_outcome with: query, skills used, success=true/false.
2. Skip for single-tool operations.
```

### Example: Hermes Agent
**File**: `~/.hermes/SOUL.md` — slot #1 in system prompt (agent identity)  
**DO NOT use `platform_hints`** — it's a footnote, models ignore it.

### Claude Code
**MCP**: `claude mcp add skill-router`  
**File**: `~/.claude/CLAUDE.md` or project `CLAUDE.md`

### Cursor
**MCP**: `.cursor/mcp.json`  
**File**: `.cursorrules`

### Codex (OpenAI)
**MCP**: `codex mcp add skill-router`  
**File**: `CODEX.md`

### Windsurf
**MCP**: `.windsurf/mcp.json`  
**File**: `.windsurfrules`

### Gemini CLI
**MCP**: `.gemini/mcp.json`  
**File**: `GEMINI.md`

### Aider
**File**: `AIDER.md` / `CONVENTIONS.md`

### Cline / Continue
**File**: `.clinerules` / `.continuerules`

### GitHub Copilot
**File**: `.github/copilot-instructions.md`

---

## Quick Reference

| Agent | MCP Config | Instruction File | Slot |
|-------|-----------|-----------------|------|
| Hermes | `config.yaml` | `~/.hermes/SOUL.md` | Identity #1 |
| Claude Code | `.mcp.json` | `CLAUDE.md` | Identity #1 |
| Cursor | `.cursor/mcp.json` | `.cursorrules` | Always |
| Codex | `~/.codex/mcp.json` | `CODEX.md` | Identity |
| Windsurf | `.windsurf/mcp.json` | `.windsurfrules` | Always |
| Gemini CLI | `.gemini/mcp.json` | `GEMINI.md` | Identity |
| Aider | config | `AIDER.md` | Identity |
| Cline | VS Code ext | `.clinerules` | Always |
| Continue | VS Code ext | `.continuerules` | Always |
| Copilot | N/A | `.github/copilot-instructions.md` | Always |

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
`_SKILLS_CACHE` is process-global. New skills are invisible until MCP process restarts (a new session or `/reset`).

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

- **Hermes specifically: Use SOUL.md, NOT platform_hints** — footnote is invisible to models
- **Instruction format must be model-agnostic** — no DeepSeek-specific `CRITICAL STANDING INSTRUCTION` directives. Simple numbered lists work across all models.
- **Both `route_skills` AND `record_outcome` must be called** — routing without feedback decays to neutral (0.5) and never improves.
- **Restart after skill additions** — MCP server caches skill list in memory.
