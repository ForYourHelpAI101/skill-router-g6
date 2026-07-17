"""
Skill Router G6 — MCP Server
Exposes G6 routing as MCP tools for Claude Desktop.

Tools:
  route_skills(query, k=5)     — returns best skill names for a query
  record_outcome(query, skills, success) — self-learning feedback
  router_stats()               — handbook + history stats
  router_history()             — last 10 routing decisions
"""

import json, sys, os
sys.path.insert(0, r"C:\Skill-Router G1")

from harness_g6 import route_g6, record_outcome, _load_json, _save_json
from harness_g6 import HANDBOOK_PATH, HISTORY_PATH, POSTERIOR_PATH
from datetime import datetime

# ── MCP stdio transport (no external deps) ──────────────────────────────────

def send(obj: dict):
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

def recv() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())

# ── Tool implementations ─────────────────────────────────────────────────────

def tool_route_skills(args: dict) -> str:
    query = args.get("query", "").strip()
    k = int(args.get("k", 5))
    if not query:
        return "Error: query is required"
    skills, explanation = route_g6(query, k=k, explain=True)
    return f"Recommended skills for: \"{query[:60]}\"\n\n{explanation}\n\nFinal: {', '.join(skills)}"

def tool_record_outcome(args: dict) -> str:
    query = args.get("query", "")
    skills = args.get("skills", [])
    success = bool(args.get("success", True))
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    record_outcome(query, skills, success)
    status = "success" if success else "failure"
    return f"Recorded {status} for {skills} on query: \"{query[:60]}\""

def tool_router_stats(args: dict) -> str:
    h = _load_json(HANDBOOK_PATH, {})
    p = _load_json(POSTERIOR_PATH, {})
    hist = _load_json(HISTORY_PATH, [])
    lines = [
        f"Skill Router G6 Stats",
        f"  Handbook:  {len(h)} skills tracked",
        f"  Posteriors:{len(p)} skills with Beta priors",
        f"  History:   {len(hist)} past routing decisions",
    ]
    if h:
        top = sorted(h.items(), key=lambda x: x[1].get("hits", 0) / max(x[1].get("n", 1), 1), reverse=True)[:5]
        lines.append("\nTop 5 by competence:")
        for name, d in top:
            n, hits = d.get("n", 0), d.get("hits", 0)
            lines.append(f"  {name}: {hits}/{n} ({hits/max(n,1)*100:.0f}%)")
    return "\n".join(lines)

def tool_router_history(args: dict) -> str:
    hist = _load_json(HISTORY_PATH, [])
    if not hist:
        return "No routing history yet."
    lines = [f"Last {min(10, len(hist))} routing decisions:"]
    for e in hist[-10:]:
        ts = datetime.fromtimestamp(e.get("ts", 0)).strftime("%m-%d %H:%M")
        icon = "+" if e.get("success") else "-"
        skills = ", ".join(e.get("skills", []))
        query = e.get("query", "")[:55]
        lines.append(f"  [{ts}] {icon} {query!r} -> {skills}")
    return "\n".join(lines)

# ── Tool registry ────────────────────────────────────────────────────────────

TOOLS = {
    "route_skills": {
        "fn": tool_route_skills,
        "description": "Find the best Hermes skills for a given task or user query using G6 agentic self-learning router",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user task or prompt to route"},
                "k":     {"type": "integer", "description": "Number of skills to return (default 5)", "default": 5}
            },
            "required": ["query"]
        }
    },
    "record_outcome": {
        "fn": tool_record_outcome,
        "description": "Record whether routed skills were helpful — feeds the self-learning loop",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":   {"type": "string", "description": "The original task/query"},
                "skills":  {"description": "Skills that were used", "oneOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "string", "description": "Comma-separated skill names"}
                ]},
                "success": {"type": "boolean", "description": "Were the skills helpful?", "default": True}
            },
            "required": ["query", "skills"]
        }
    },
    "router_stats": {
        "fn": tool_router_stats,
        "description": "Show Skill Router G6 stats: handbook, posteriors, history counts and top competent skills",
        "inputSchema": {"type": "object", "properties": {}}
    },
    "router_history": {
        "fn": tool_router_history,
        "description": "Show the last 10 routing decisions for debugging and audit",
        "inputSchema": {"type": "object", "properties": {}}
    },
}

# ── MCP protocol handler ─────────────────────────────────────────────────────

def handle(req: dict) -> dict | None:
    method = req.get("method", "")
    rid    = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "skill-router-g6", "version": "6.0.0"}
            }
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": info["description"],
                        "inputSchema": info["inputSchema"]
                    }
                    for name, info in TOOLS.items()
                ]
            }
        }

    if method == "tools/call":
        params    = req.get("params", {})
        tool_name = params.get("name", "")
        args      = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            }
        try:
            result_text = TOOLS[tool_name]["fn"](args)
        except Exception as e:
            result_text = f"Error: {e}"
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": False
            }
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}

    # Unknown method — return error
    if rid is not None:
        return {
            "jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }
    return None

# ── Main loop ────────────────────────────────────────────────────────────────

def main():
    while True:
        try:
            req = recv()
        except (json.JSONDecodeError, ValueError):
            continue
        if req is None:
            break
        try:
            resp = handle(req)
        except Exception as e:
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {"code": -32603, "message": str(e)}
            }
        if resp is not None:
            send(resp)

if __name__ == "__main__":
    main()
