---
name: skill-router-g6
description: G6 self-learning skill router — RAG history match, keyword patterns, BM25 body retrieval, Thompson sampling, SkillOrchestra competence tracking, DPP diversity. Agent-agnostic: picks best skills for any task from any agent's skill directory (Hermes, Claude Code, Cursor, Codex, Windsurf, Gemini CLI, or a custom path).
version: G6
---

# Skill-Router G6

Self-learning skill selection: 6-stage pipeline, anti-hallucination gate.

## Location
```
C:\Skill-Router G1\
├── harness_g1.py         CURRENT — 6-stage self-learning router, "G6" pipeline (imported by mcp_server.py + hermes_hook.py; filename matches this folder's name, not the algorithm generation)
├── mcp_server.py         MCP stdio server exposing route_skills/record_outcome/router_stats/router_history
├── hermes_hook.py        Thin wrapper -> harness_g1.hook_main() for hooks.pre_llm_call
├── AGENT_INTEGRATION.md  Cross-agent wiring guide
├── SKILL.md              This file

_archive\  — superseded generations + dead/broken files, moved out 2026-07-18, not imported by anything live:
├── harness.py, harness_g1.py..g5.py, harness_hybrid.py, harness_unified.py  (prior generations)
│     ⚠️ _archive\harness_g1.py is the ORIGINAL generation-1 script — unrelated content to the
│     active C:\Skill-Router G1\harness_g1.py above, which is the renamed G6 pipeline. Same
│     filename, different code, different folder. Don't copy one over the other by habit.
├── skill_router_hook.py  (standalone G5 keyword-only fast-path, was never wired into config.yaml)
├── hermes_hook.sh        (broken — pointed at nonexistent hook_main.py)
```

## Portability
`harness_g1.py` now auto-detects the skills directory across agents (Hermes, Claude Code, Codex,
Cursor, Windsurf, Gemini CLI, or any `SKILL_ROUTER_SKILLS_DIR` you set explicitly) — no source
edits needed to point it at a different agent. See AGENT_INTEGRATION.md → "Skills Directory
Resolution" for the priority order and env vars. Cache/handbook/history stay scoped per-agent
by default (`<skills_dir>/../.router-cache`), so routing history doesn't bleed across agents
unless you deliberately point two at the same `SKILLS_DIR`.

## Active wiring (as of 2026-07-18)
Registered in `%LOCALAPPDATA%\hermes\config.yaml`:
- `mcp_servers.skill-router` → `mcp_server.py` (MCP tool mode — available on demand, not force-instructed)
- `hooks.pre_llm_call` → `hermes_hook.py` (deterministic harness mode — the single active routing trigger)

Previously had `shell_hooks` (duplicate hook) and `platform_hints.*.append` (LLM-driven MCP-call
instruction) also firing on every message — both removed 2026-07-18 to eliminate 2-3x redundant
routing calls per turn. Harness mode alone is sufficient per AGENT_INTEGRATION.md's own guidance
("harness injection... OR direct MCP tool calls", not both).

## Pipeline (6-stage, ~100-900ms)

```
Query → [RAG History] + [Keyword Match] + [BM25 Body Retrieval]
            ↓                          ↓
     [Thompson Boost]  ←  [Handbook Competence]
            ↓
     [DPP-Greedy Diversity] → Final top-k skills
     ↓
  FINAL GATE: drop anything not in handbook (anti-hallucination)
```

Self-learning: `record_outcome()` updates Beta posteriors + handbook competence from task outcomes.

## Usage

```bash
cd "C:\Skill-Router G1"
python harness_g1.py "deploy kubernetes to azure with monitoring"
python harness_g1.py --stats
python harness_g1.py --history
python harness_g1.py "<query>" --feedback <skill1> <skill2> success|fail
```

## Known limitations (tracked, not yet fixed)
- `quick_match()` PATTERNS list is empty in harness_g1.py — keyword stage currently contributes nothing (intentionally — no hardcoded skill-name list is kept in source; see git/edit history if reinstating one).
