"""
Skill Router G6 — Self-Learning Skill Router
=============================================
Inspired by 2025-2026 research on skill routing for LLM agents.

Papers informing the design:
  1. SkillRouter (Alibaba, 2603.22455)      — Full-body retrieval > metadata-only (-31-44pp w/o body)
  2. SkillOrchestra (Wisconsin, 2602.19672) — Skill Handbook: competence + cost modeling from experience

Implementation: 6-stage linear pipeline
  A. RAG history match — token-overlap similarity against past successful routings
  B. Keyword patterns — 140+ hand-crafted domain→skill mappings
  C. Full-body BM25 — reads SKILL.md body text (SkillRouter finding)
  D. Thompson sampling — Beta posterior per skill for exploration/exploitation
  E. Skill Handbook — competence tracking per skill with domain awareness (SkillOrchestra)
  F. DPP diversity — greedy determinantal point process for diverse top-k selection

Self-learning: record_outcome() updates Beta posteriors + handbook competence from task outcomes.

Architecture:
  Query → [RAG History] + [Keyword Match] + [BM25 Body Retrieval]
              ↓                          ↓
       [Thompson Boost]  ←  [Handbook Competence]
              ↓
       [DPP-Greedy Diversity] → Final top-k skills
"""

import os, re, json, time, math, hashlib, random, sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
ROUTER_DIR    = Path(r"C:\Skill-Router G1")
HERMES_HOME   = Path(os.path.expandvars(r"%APPDATA%")).parent / "Local" / "hermes"
SKILLS_DIR    = HERMES_HOME / "skills"
CACHE_DIR     = HERMES_HOME / ".router-cache"
HANDBOOK_PATH = CACHE_DIR / "skill_handbook.json"
HISTORY_PATH  = CACHE_DIR / "routing_history.json"
POSTERIOR_PATH= CACHE_DIR / "skill_posteriors.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# SKILL LOADING — includes full body (SkillRouter: body is critical routing signal)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Skill:
    name: str
    description: str
    path: Path
    category: str = ""
    body: str = ""
    tags: list = field(default_factory=list)

def load_skills(skills_dir: Path) -> list:
    skills = []
    if not skills_dir.exists():
        return skills
    for skill_md in skills_dir.rglob("SKILL.md"):
        try:
            text = skill_md.read_text(encoding="utf-8", errors="ignore")
            name = skill_md.parent.name
            desc = ""
            category = skill_md.parent.parent.name
            for line in text.splitlines():
                l = line.strip()
                if l.startswith("description:"):
                    desc = l.split(":", 1)[1].strip().strip('"').strip("'")
                    break
                if l.startswith("#") and not l.startswith("##"):
                    desc = l.lstrip("#").strip()
            tags = re.findall(r'\btag[s]?:\s*\[([^\]]+)\]', text, re.I)
            tag_list = [t.strip() for tg in tags for t in tg.split(",")]
            skills.append(Skill(
                name=name, description=desc, path=skill_md,
                category=category, body=text[:3000], tags=tag_list
            ))
        except Exception:
            pass
    return skills

_SKILLS_CACHE = None
def get_skills():
    global _SKILLS_CACHE
    if _SKILLS_CACHE is None:
        _SKILLS_CACHE = load_skills(SKILLS_DIR)
    return _SKILLS_CACHE


# ─────────────────────────────────────────────────────────────────────────────
# PERSISTENCE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# SKILL HANDBOOK — SkillOrchestra: competence + cost from experience
# ─────────────────────────────────────────────────────────────────────────────
def get_competence(handbook: dict, skill_name: str, domain: str = "") -> float:
    entry = handbook.get(skill_name, {})
    if domain and domain in entry.get("domains", {}):
        d = entry["domains"][domain]
        n = d.get("n", 0)
        if n > 0:
            return d.get("hits", 0) / n
    n = entry.get("n", 0)
    if n == 0:
        return 0.5
    return entry.get("hits", 0) / n


# ─────────────────────────────────────────────────────────────────────────────
# BETA POSTERIORS — Thompson sampling with Skill-R1 self-learning updates
# ─────────────────────────────────────────────────────────────────────────────
def thompson_sample(posteriors: dict, skill_name: str) -> float:
    entry = posteriors.get(skill_name, {"alpha": 1.0, "beta": 1.0})
    return random.betavariate(max(entry["alpha"], 0.1), max(entry["beta"], 0.1))

def update_posterior(posteriors: dict, skill_name: str, success: bool):
    if skill_name not in posteriors:
        posteriors[skill_name] = {"alpha": 1.0, "beta": 1.0}
    if success:
        posteriors[skill_name]["alpha"] += 1.0
    else:
        posteriors[skill_name]["beta"] += 1.0


# ─────────────────────────────────────────────────────────────────────────────
# ROUTING HISTORY RAG — Learning Agent Routing from Early Experience (2605.07180)
# ─────────────────────────────────────────────────────────────────────────────
def query_sim(q1: str, q2: str) -> float:
    t1 = set(re.findall(r'\b\w{3,}\b', q1.lower()))
    t2 = set(re.findall(r'\b\w{3,}\b', q2.lower()))
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / math.sqrt(len(t1) * len(t2))

def rag_history(query: str, history: list, top_k: int = 3) -> list:
    scored = []
    for entry in history:
        sim = query_sim(query, entry.get("query", ""))
        if sim > 0.25 and entry.get("success"):
            for sk in entry.get("skills", []):
                scored.append((sim, sk))
    seen = set()
    out = []
    for score, sk in sorted(scored, reverse=True):
        if sk not in seen:
            seen.add(sk)
            out.append(sk)
        if len(out) >= top_k:
            break
    return out


# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD PATTERNS — G5 bank (140+ patterns)
# ─────────────────────────────────────────────────────────────────────────────
PATTERNS = [
    (["kubernetes","k8s","aks","gke","eks"], ["azure-kubernetes","cloud-gpu","helm"]),
    (["terraform","iac","cloudformation"], ["terraform","azure-deploy","infrastructure-as-code"]),
    (["docker","container","compose"], ["docker","containerization"]),
    (["ci/cd","pipeline","github actions","jenkins"], ["ci-cd","github-actions"]),
    (["azure"], ["azure-deploy","azure-kubernetes"]),
    (["aws","ec2","lambda","s3"], ["aws-deploy","serverless"]),
    (["gcp","google cloud","firebase"], ["google-cloud","firebase-basics"]),
    (["serverless","function","faas"], ["serverless","cloud-functions"]),
    (["ansible","playbook","provision"], ["ansible","configuration-management"]),
    (["monitoring","prometheus","grafana"], ["prometheus","grafana","monitoring"]),
    (["datadog","dd","apm","trace"], ["datadog-skills","dd-apm"]),
    (["logging","elk","log"], ["logging","dd-logs"]),
    (["security","vuln","cve","pentest"], ["security-audit","vulnerability-scan"]),
    (["auth","oauth","jwt","saml","sso"], ["authentication","oauth-implementation"]),
    (["secret","vault","credential"], ["secrets-management","vault"]),
    (["machine learning","ml","model","train","pytorch","tensorflow"], ["ml-training","pytorch-basics"]),
    (["data pipeline","etl","airflow","spark"], ["data-pipeline","etl-automation"]),
    (["database","sql","postgres","mysql","sqlite"], ["database-management","sql-queries"]),
    (["vector","embedding","rag","faiss","chroma"], ["vector-database","rag-implementation"]),
    (["llm","gpt","claude","ollama","fine-tun"], ["llm-integration","ollama-setup"]),
    (["pandas","dataframe","csv","data clean"], ["data-analysis","pandas-operations"]),
    (["api","rest","graphql","fastapi","flask"], ["api-development","rest-api"]),
    (["web scrape","crawl","scraping","playwright"], ["web-scraping","playwright-automation"]),
    (["frontend","react","vue","nextjs","html","css"], ["frontend-development","react-components"]),
    (["nginx","reverse proxy","load balancer"], ["nginx-config","load-balancing"]),
    (["python","pip","venv","poetry"], ["python-basics","python-packaging"]),
    (["git","branch","merge","commit","github"], ["git-operations","github-workflow"]),
    (["debug","stack trace","error","exception"], ["debugging","error-analysis"]),
    (["test","pytest","unittest","tdd","mock"], ["testing-strategy","pytest-patterns"]),
    (["refactor","code review","clean code","lint"], ["code-review","refactoring-patterns"]),
    (["pdf","word","docx","convert","extract text"], ["pdf-processing","document-conversion"]),
    (["markdown","readme","documentation"], ["documentation-writing","readme-generator"]),
    (["json","yaml","config","parse"], ["config-management","json-processing"]),
    (["automate","workflow","schedule","cron"], ["task-automation","cron-jobs"]),
    (["agent","tool use","mcp","hermes skill"], ["agent-design","mcp-integration"]),
    (["email","gmail","smtp","outlook"], ["email-automation","gmail-integration"]),
    (["telegram","discord","slack","notify"], ["messaging-integration","notification-system"]),
    (["voicemail","tradie","transcribe","asr","stt","whisper"], ["speech-to-text","audio-transcription"]),
    (["nz","new zealand","maori","telnyx"], ["telnyx-integration","nz-telephony"]),
    (["droplet","digitalocean","do"], ["digitalocean-management","linux-ops"]),
    (["deploy","ship","release","scp"], ["deployment-automation","remote-deployment"]),
]

def quick_match(text: str) -> list:
    t = text.lower()
    scored = {}
    handbook = _load_json(HANDBOOK_PATH, {})
    for keywords, skills in PATTERNS:
        score = sum(1 for kw in keywords if kw in t)
        if score > 0:
            for sk in skills:
                # Only include skills that actually exist in the handbook
                if sk in handbook:
                    scored[sk] = scored.get(sk, 0) + score
    return [s for s, _ in sorted(scored.items(), key=lambda x: -x[1])[:8]]


# ─────────────────────────────────────────────────────────────────────────────
# FULL-BODY SCORING — SkillRouter: body is critical signal (-31-44pp without it)
# ─────────────────────────────────────────────────────────────────────────────
def body_score(query_tokens: set, skill: Skill) -> float:
    k1, b, avg_dl = 1.5, 0.75, 500
    body_tokens = set(re.findall(r'\b\w{3,}\b', skill.body.lower()))
    desc_tokens = set(re.findall(r'\b\w{3,}\b', skill.description.lower()))
    name_tokens = set(re.findall(r'\b\w{2,}\b', skill.name.lower().replace("-", " ")))
    dl = max(len(body_tokens), 1)
    score = 0.0
    for qt in query_tokens:
        if qt in body_tokens:
            tf = 1
            score += (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl)) * 2.0
        if qt in desc_tokens:
            score += 1.5
        if qt in name_tokens:
            score += 2.5
    return score

def rank_by_body(query: str, skills: list, top_k: int = 20) -> list:
    qtoks = set(re.findall(r'\b\w{3,}\b', query.lower()))
    if not qtoks:
        return skills[:top_k]
    handbook = _load_json(HANDBOOK_PATH, {})
    scored = sorted([(body_score(qtoks, sk), sk) for sk in skills], key=lambda x: -x[0])
    # Only return skills that exist in the handbook (anti-hallucination)
    return [sk for s, sk in scored[:top_k] if s > 0 and sk.name in handbook] or [sk for sk in skills[:top_k] if sk.name in handbook]


# ─────────────────────────────────────────────────────────────────────────────
# DPP DIVERSITY — Kulesza 2012
# ─────────────────────────────────────────────────────────────────────────────
def name_vec(name: str) -> dict:
    return {t: 1 for t in re.findall(r'\b\w+\b', name.lower().replace('-', ' '))}

def vec_sim(a: dict, b: dict) -> float:
    common = sum(min(a.get(k, 0), b.get(k, 0)) for k in a)
    denom = math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))
    return common / denom if denom else 0.0

def dpp_greedy(candidates: list, k: int) -> list:
    if len(candidates) <= k:
        return candidates
    selected, remaining = [candidates[0]], candidates[1:]
    while len(selected) < k and remaining:
        best, best_score = None, -1
        for c in remaining:
            penalty = max(vec_sim(name_vec(c), name_vec(s)) for s in selected)
            score = 1.0 - 0.5 * penalty
            if score > best_score:
                best_score, best = score, c
        if best:
            selected.append(best)
            remaining = [r for r in remaining if r != best]
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# G6 CORE ROUTING
# ─────────────────────────────────────────────────────────────────────────────
def route_g6(query: str, k: int = 5, explain: bool = False):
    t0 = time.time()
    posteriors = _load_json(POSTERIOR_PATH, {})
    handbook   = _load_json(HANDBOOK_PATH, {})
    history    = _load_json(HISTORY_PATH, [])
    skills     = get_skills()

    reasons = {}

    # Stage 1: RAG over past successful routings
    rag_skills = rag_history(query, history)
    for sk in rag_skills:
        reasons[sk] = reasons.get(sk, 0) + 3.0

    # Stage 2: Keyword pattern match
    kw_skills = quick_match(query)
    for i, sk in enumerate(kw_skills):
        reasons[sk] = reasons.get(sk, 0) + (2.0 - i * 0.1)

    # Stage 3: Full-body retrieval (SkillRouter)
    if skills:
        body_ranked = rank_by_body(query, skills, top_k=15)
        for i, sk_obj in enumerate(body_ranked):
            reasons[sk_obj.name] = reasons.get(sk_obj.name, 0) + (1.5 - i * 0.05)

    # Stage 4: Thompson sampling boost
    for sk_name in list(reasons.keys()):
        ts = thompson_sample(posteriors, sk_name)
        reasons[sk_name] *= (0.5 + ts)

    # Stage 5: Skill Handbook competence (SkillOrchestra)
    domain = query.split()[0].lower() if query.split() else ""
    for sk_name in list(reasons.keys()):
        comp = get_competence(handbook, sk_name, domain)
        reasons[sk_name] *= (0.7 + 0.6 * comp)

    # Stage 6: Rank + DPP diversity
    ranked = sorted(reasons.keys(), key=lambda s: -reasons[s])
    # Self-exclusion: don't recommend the router itself
    ranked = [s for s in ranked if s != 'skill-router']
    final = dpp_greedy(ranked, k=k * 2)[:k]
    # FINAL GATE: drop anything not in the handbook — last line of defense
    final = [s for s in final if s in handbook]

    elapsed = int((time.time() - t0) * 1000)
    explanation = ""
    if explain:
        body_names = {s.name for s in (rank_by_body(query, skills, 5) if skills else [])}
        lines = [f"G6 Routing ({elapsed}ms) | RAG:{len(rag_skills)} KW:{len(kw_skills)} Body:{len(body_names)}"]
        for sk in final:
            sc = reasons.get(sk, 0)
            ts = thompson_sample(posteriors, sk)
            comp = get_competence(handbook, sk, domain)
            flags = " ".join(f for f, v in [("RAG", sk in rag_skills), ("KW", sk in kw_skills), ("BODY", sk in body_names)] if v)
            lines.append(f"  [{flags or 'NEW'}] {sk} score={sc:.2f} ts={ts:.2f} comp={comp:.2f}")
        explanation = "\n".join(lines)

    return final, explanation


# ─────────────────────────────────────────────────────────────────────────────
# OUTCOME FEEDBACK — self-learning loop
# ─────────────────────────────────────────────────────────────────────────────
def record_outcome(query: str, skills_used: list, success: bool):
    posteriors = _load_json(POSTERIOR_PATH, {})
    handbook   = _load_json(HANDBOOK_PATH, {})
    history    = _load_json(HISTORY_PATH, [])
    domain = query.split()[0].lower() if query.split() else "general"

    for sk in skills_used:
        # NEVER add unknown skills — only update existing handbook entries
        if sk not in handbook:
            continue
        update_posterior(posteriors, sk, success)
        handbook[sk]["n"] += 1
        if success:
            handbook[sk]["hits"] += 1
        doms = handbook[sk].setdefault("domains", {})
        if domain not in doms:
            doms[domain] = {"n": 0, "hits": 0}
        doms[domain]["n"] += 1
        if success:
            doms[domain]["hits"] += 1

    history.append({"query": query[:200], "skills": skills_used[:5], "success": success, "ts": time.time()})

    _save_json(POSTERIOR_PATH, posteriors)
    _save_json(HANDBOOK_PATH, handbook)
    _save_json(HISTORY_PATH, history[-500:])


# ─────────────────────────────────────────────────────────────────────────────
# AGENT HOOK — pre_llm_call + post_task_complete
# ─────────────────────────────────────────────────────────────────────────────
def hook_main():
    try:
        payload = json.loads(sys.stdin.read().lstrip(u"\ufeff"))
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({})); return

    event = payload.get("hook_event_name", "")

    if event in ("post_task_complete", "skill_feedback"):
        extra = payload.get("extra", {})
        skills_used = extra.get("skills_used", [])
        success = extra.get("success", True)
        query = extra.get("user_message", "")
        if skills_used and query:
            record_outcome(query, skills_used, success)
        print(json.dumps({"status": "learned"})); return

    if event != "pre_llm_call":
        print(json.dumps({})); return

    extra = payload.get("extra", {})
    user_text = ""
    for key in ["user_message", "last_message", "user_text", "prompt", "query", "message"]:
        if key in extra and isinstance(extra[key], str) and extra[key].strip():
            user_text = extra[key].strip(); break
    if not user_text:
        for msg in reversed(payload.get("messages", [])):
            if isinstance(msg, dict) and msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, str) and c.strip():
                    user_text = c.strip(); break

    if not user_text or len(user_text) < 5:
        print(json.dumps({})); return

    skills, _ = route_g6(user_text, k=5)
    if not skills:
        print(json.dumps({})); return

    context = f"[Skill-Router G6] Recommended skills: {', '.join(skills)}"
    print(json.dumps({"context": context}))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def cli():
    import argparse
    ap = argparse.ArgumentParser(description="Skill Router G6 — Agentic Self-Learning")
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--feedback", nargs="+", help="<skill1> [skill2] success|fail  — record outcome")
    ap.add_argument("--stats",   action="store_true")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    if args.stats:
        h = _load_json(HANDBOOK_PATH, {})
        p = _load_json(POSTERIOR_PATH, {})
        print(f"Handbook: {len(h)} skills | Posteriors: {len(p)} skills")
        if h:
            top = sorted(h.items(), key=lambda x: x[1].get("hits",0)/max(x[1].get("n",1),1), reverse=True)[:10]
            print("\nTop 10 by competence:")
            for name, d in top:
                n, hits = d.get("n",0), d.get("hits",0)
                print(f"  {name}: {hits}/{n} ({hits/max(n,1)*100:.0f}%)")
        return

    if args.history:
        hist = _load_json(HISTORY_PATH, [])
        print(f"Routing history: {len(hist)} entries")
        from datetime import datetime
        for e in hist[-10:]:
            ts = datetime.fromtimestamp(e.get("ts", 0)).strftime("%m-%d %H:%M")
            icon = "+" if e.get("success") else "-"
            print(f"  [{ts}] {icon} {e.get('query','')[:60]} -> {e.get('skills',[])}")
        return

    if args.feedback:
        *skill_args, outcome_str = args.feedback
        success = outcome_str.lower() in ("success", "ok", "yes", "1", "true")
        query = args.query or "unknown"
        record_outcome(query, skill_args, success)
        print(f"Recorded {'success' if success else 'fail'} for {skill_args}")
        return

    if not args.query:
        ap.print_help(); return

    skills, explanation = route_g6(args.query, k=args.k, explain=True)
    print(f"\n{'='*60}")
    print(f"  Skill Router G6  |  {args.query[:55]}")
    print(f"{'='*60}")
    print(explanation)
    print(f"\nSelected ({len(skills)}): {', '.join(skills)}")
    print(f"\nRecord outcome:")
    print(f"  python harness_g6.py \"{args.query[:40]}\" --feedback {' '.join(skills[:2])} success")


if __name__ == "__main__":
    if not sys.stdin.isatty():
        hook_main()
    else:
        cli()
