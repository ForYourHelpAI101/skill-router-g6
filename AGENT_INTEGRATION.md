# Skill Router G6 — Agent Integration Guide

Force-integrate skill routing + self-learning feedback into any AI coding agent. Model-agnostic
AND skills-source-agnostic — works with DeepSeek, Claude, GPT, Gemini, Llama, Qwen, and all
others, pointed at any agent's skill directory.

Two integration modes, pick one per agent (don't run both — redundant, inconsistent):
- **Harness mode** — agent calls a hook script before every LLM call, router runs deterministically,
  zero model compliance needed. Only available where the agent supports pre-call hooks (currently: Hermes).
- **MCP mode** — router exposed as an MCP tool (`route_skills`, `record_outcome`, `router_stats`,
  `router_history`); the model is instructed to call it itself. Works with any MCP-capable agent.

---

## 0. Before onboarding any agent

Confirm the router can see that agent's skills:
```bash
cd "C:\Skill-Router G1"
python harness_g1.py --stats
```
If the handbook count looks wrong (0, or a different agent's skill count), point it explicitly:
```bash
# Windows PowerShell
$env:SKILL_ROUTER_SKILLS_DIR = "C:\path\to\agent\skills"
# macOS/Linux
export SKILL_ROUTER_SKILLS_DIR="/path/to/agent/skills"
```
Auto-detected without any env var, in priority order: `~/.claude/skills` (Claude Code),
`~/AppData/Local/hermes/skills` (Hermes/Windows) or the Linux/macOS Hermes equivalents,
`~/.codex/skills`, `~/.cursor/skills`, `~/.windsurf/skills`, `~/.gemini/skills`,
`~/.config/skills`, then `./skills` relative to cwd as a last resort.

`SKILL_ROUTER_CACHE_DIR` follows the same resolution and defaults to `<skills_dir>/../.router-cache`
— each agent gets its own routing history/posteriors unless you deliberately point two agents at
the same dirs to share learning.

---

## The Router Instruction (MCP mode — copy-paste into whichever instruction file, model-agnostic)

```
## Router (MANDATORY)
Before replying to any substantive user message (10+ words, not a correction):
1. Call mcp__skill_router__route_skills with the user's query.
2. Show the top 5 skills on one line: 🎯 Router: a, b, c, d, e
3. If the call fails, continue silently. Skip for messages under 10 words.

After any task (5+ tool calls):
1. Call mcp__skill_router__record_outcome with: query, skills used, success=true/false.
2. Skip for single-tool operations.
```
Keep it a plain numbered list — no model-specific `CRITICAL STANDING INSTRUCTION` framing.
Some agents (e.g. Hermes `platform_hints`) treat certain config slots as low-priority footnotes
that models routinely ignore — check where the "critical" instruction actually needs to sit.

---

## Hermes — Harness mode (recommended for Hermes; zero model compliance needed)

1. Register the MCP server (optional — for on-demand `route_skills` calls outside the hook) in
   `%LOCALAPPDATA%\hermes\config.yaml` under `mcp_servers`:
   ```yaml
   mcp_servers:
     skill-router:
       command: C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe
       args: [C:\Skill-Router G1\mcp_server.py]
       enabled: true
   ```
2. Wire the deterministic hook, also in `config.yaml`:
   ```yaml
   hooks:
     pre_llm_call: '[{"command": "C:\\Skill-Router G1\\hermes_hook.py"}]'
   ```
   Do **not** also add a `shell_hooks` entry for the same script, and do **not** add the MCP
   instruction text to `platform_hints` — running harness mode plus MCP-instruction mode
   simultaneously fires the router 2-3x redundantly per message with inconsistent results.
3. Restart the Hermes gateway (module caches skill list + code in memory — see Maintenance below).
4. Verify: send a substantive message and confirm a `🎯 Router: ...` line appears in the
   injected context, or run `python harness_g1.py "<your query>"` directly to sanity-check output.

## Claude Code — MCP mode

1. Point the router at Claude Code's skills, if not already auto-detected:
   ```bash
   export SKILL_ROUTER_SKILLS_DIR="$HOME/.claude/skills"   # usually picked up automatically
   ```
2. Register the MCP server:
   ```bash
   claude mcp add skill-router -- python "C:\Skill-Router G1\mcp_server.py"
   ```
   (On macOS/Linux, use the `python3` path and forward-slash path instead.)
3. Add the router instruction block (above) to `~/.claude/CLAUDE.md` (global) or the project's
   `CLAUDE.md` (per-project) — put it near the top since Claude Code weights early identity
   content more heavily.
4. Restart the Claude Code session (`/mcp` to confirm `skill-router` shows connected, or check
   `claude mcp list`).
5. Verify: ask a substantive question and confirm `🎯 Router: ...` appears before the answer.

---

## Cursor — MCP mode

1. Point the router: `export SKILL_ROUTER_SKILLS_DIR="$HOME/.cursor/skills"` if your skills
   don't live in the default Cursor location — Cursor doesn't standardize a skills folder the
   way Claude Code does, so check what you're actually indexing with `--stats` first.
2. Add the server to `.cursor/mcp.json` (project) or the global Cursor MCP config:
   ```json
   {
     "mcpServers": {
       "skill-router": {
         "command": "python",
         "args": ["C:\\Skill-Router G1\\mcp_server.py"]
       }
     }
   }
   ```
3. Add the router instruction block to `.cursorrules` in the project root.
4. Reload the Cursor window (Cmd/Ctrl+Shift+P → "Reload Window") so it picks up the new MCP server.
5. Verify: open Cursor's MCP settings panel and confirm `skill-router` is listed as connected
   with 4 tools (`route_skills`, `record_outcome`, `router_stats`, `router_history`).

## Codex (OpenAI) — MCP mode

1. Point the router: `export SKILL_ROUTER_SKILLS_DIR="$HOME/.codex/skills"` if needed.
2. Register the MCP server:
   ```bash
   codex mcp add skill-router -- python "C:\Skill-Router G1\mcp_server.py"
   ```
3. Add the router instruction block to `CODEX.md` in the project root or Codex's global
   instructions file.
4. Restart the Codex session.
5. Verify: run a task and confirm the router line appears; check Codex's MCP status output
   (command varies by version — consult `codex mcp --help` if `codex mcp list` doesn't exist
   in your installed version) for `skill-router` as connected.

---

## Windsurf — MCP mode

1. Point the router: `export SKILL_ROUTER_SKILLS_DIR="$HOME/.windsurf/skills"` if needed.
2. Add the server to `.windsurf/mcp.json`:
   ```json
   {
     "mcpServers": {
       "skill-router": {
         "command": "python",
         "args": ["C:\\Skill-Router G1\\mcp_server.py"]
       }
     }
   }
   ```
3. Add the router instruction block to `.windsurfrules` in the project root.
4. Reload Windsurf (or restart the Cascade panel) so the new MCP server registers.
5. Verify: check Windsurf's MCP tool panel for `skill-router` with 4 tools listed, then run a
   task and confirm the router line appears.

## Gemini CLI — MCP mode

1. Point the router: `export SKILL_ROUTER_SKILLS_DIR="$HOME/.gemini/skills"` if needed.
2. Add the server to `.gemini/mcp.json`:
   ```json
   {
     "mcpServers": {
       "skill-router": {
         "command": "python",
         "args": ["C:\\Skill-Router G1\\mcp_server.py"]
       }
     }
   }
   ```
3. Add the router instruction block to `GEMINI.md` in the project root.
4. Restart the Gemini CLI session.
5. Verify: run `/mcp` (or the current equivalent status command) and confirm `skill-router`
   is listed; then run a task and check for the router line.

---

## Aider — no MCP support (file-context only, not a live tool call)

Aider does not call MCP tools directly. You can still steer it toward the right skill files:
1. Add a short static block to `AIDER.md` or `CONVENTIONS.md` describing available skill
   categories (pull the list from `python harness_g1.py --stats` output) so Aider's context
   includes what's available.
2. For a live routing decision, run `python harness_g1.py "<task description>"` yourself before
   starting the Aider session, and paste the top skill names into your first Aider prompt.
3. There's no automated feedback loop here — `record_outcome` has to be called manually via CLI
   (`python harness_g1.py "<query>" --feedback <skill1> <skill2> success|fail`) if you want this
   session to improve the Beta posteriors.

---

## Cline / Continue (VS Code extensions) — MCP mode

1. Point the router: `export SKILL_ROUTER_SKILLS_DIR="$HOME/.vscode/skills"` or wherever that
   extension's skills actually live — check with `--stats`.
2. Add the server through the extension's MCP settings (Cline: Settings → MCP Servers → Configure;
   Continue: `.continue/mcpServers/skill-router.yaml` or the extension's MCP config panel,
   depending on version):
   ```json
   {
     "skill-router": {
       "command": "python",
       "args": ["C:\\Skill-Router G1\\mcp_server.py"]
     }
   }
   ```
3. Add the router instruction block to `.clinerules` (Cline) or `.continuerules` (Continue).
4. Reload the VS Code window.
5. Verify: open the extension's MCP server list and confirm `skill-router` is connected.

## GitHub Copilot — MCP mode (version-dependent)

Copilot Chat's MCP support and config location has changed across releases — check
GitHub's current docs for your installed version before following this blindly.
1. Add the server to VS Code's `settings.json` under the Copilot/MCP section, or
   `.vscode/mcp.json` if your version uses a project-level file:
   ```json
   {
     "servers": {
       "skill-router": {
         "command": "python",
         "args": ["C:\\Skill-Router G1\\mcp_server.py"]
       }
     }
   }
   ```
2. Add the router instruction block to `.github/copilot-instructions.md`.
3. Reload VS Code.
4. Verify: open Copilot Chat's tool/MCP picker and confirm `skill-router` is available.

---

## Quick Reference

| Agent | Mode | MCP Config | Instruction File |
|-------|------|-----------|-------------------|
| Hermes | Harness (recommended) | `config.yaml` `mcp_servers` (optional) | n/a — hook is deterministic |
| Claude Code | MCP | `claude mcp add` | `CLAUDE.md` |
| Cursor | MCP | `.cursor/mcp.json` | `.cursorrules` |
| Codex | MCP | `codex mcp add` | `CODEX.md` |
| Windsurf | MCP | `.windsurf/mcp.json` | `.windsurfrules` |
| Gemini CLI | MCP | `.gemini/mcp.json` | `GEMINI.md` |
| Aider | Manual (no MCP) | n/a | `AIDER.md` / `CONVENTIONS.md` |
| Cline | MCP | extension settings | `.clinerules` |
| Continue | MCP | extension settings | `.continuerules` |
| Copilot | MCP (version-dependent) | `settings.json` / `.vscode/mcp.json` | `.github/copilot-instructions.md` |

---

## Architecture

6-stage linear pipeline:

```
Query → [RAG History] + [Keyword Match] + [BM25 Body Retrieval]
            ↓                          ↓
     [Thompson Boost]  ←  [Handbook Competence]
            ↓
     [DPP-Greedy Diversity] → Final top-5 skills
```

Self-learning: `record_outcome()` updates Beta posteriors per skill + handbook competence from
task outcomes. Thompson sampling balances exploration/exploitation. Keyword-match stage is
currently a no-op (empty `PATTERNS` list by design — see `SKILL.md` known limitations).

---

## Maintenance

### Bootstrap / Rebuild Handbook
```bash
python -c "
import sys; sys.path.insert(0, 'C:/Skill-Router G1')
from harness_g1 import get_skills, _save_json, CACHE_DIR, HANDBOOK_PATH
CACHE_DIR.mkdir(parents=True, exist_ok=True)
import harness_g1; harness_g1._SKILLS_CACHE = None
skills = get_skills()
handbook = {s.name: {'n':0,'hits':0,'domains':{}} for s in skills}
_save_json(HANDBOOK_PATH, handbook)
print(f'Handbook: {len(handbook)} skills')
"
```

### Nuke Hallucinated History
Cache location depends on which agent's `SKILLS_DIR` is active (see section 0 above) — check
`$env:SKILL_ROUTER_CACHE_DIR` or run `python harness_g1.py --stats` first if unsure which
handbook/history file is currently in play.
```bash
python -c "from harness_g1 import HISTORY_PATH, _save_json; _save_json(HISTORY_PATH, [])"
```

### MCP Server Cache
`_SKILLS_CACHE` is process-global. New skills are invisible until the MCP process (or hook
process, for Hermes harness mode) restarts — new agent session, or that agent's equivalent of
a tool/MCP reload command.

---

## Anti-Hallucination Protections

| Layer | Protection |
|-------|-----------|
| Keyword patterns | Cross-checked against handbook before returning (stage currently a no-op, see above) |
| record_outcome | Only updates existing handbook entries — never adds unknowns |
| Handbook | Rebuilt from SKILL.md files with content validation |
| Final gate | route_g6() drops anything not present in the handbook as a last line of defense |

---

## ⚠️ Critical Notes

- **Pick ONE mode per agent** — harness mode and MCP-instruction mode fired simultaneously is
  redundant and gives inconsistent Thompson-sampled results per call (this bit Hermes; fixed
  2026-07-18 by removing the duplicate `shell_hooks` entry and `platform_hints` instruction).
- **Instruction format must be model-agnostic** — no vendor-specific "CRITICAL STANDING
  INSTRUCTION" framing. Simple numbered lists work across all models.
- **Both `route_skills` AND `record_outcome` must be called** — routing without feedback decays
  to neutral (0.5) and never improves.
- **Restart after skill additions** — the process caches the skill list in memory.
- **Check where "critical" instructions actually get weighted** — some agents' config slots
  (e.g. Hermes `platform_hints`) are low-priority footnotes models routinely ignore; confirm the
  instruction file you're using actually lands in a slot the model reliably reads.
