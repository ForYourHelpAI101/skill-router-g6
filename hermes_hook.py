"""Skill-Router G6 — Hermes Hook (Ralph Loop)
Wired via config.yaml:
  hooks:
    pre_llm_call:
      - command: "/c/Skill-Router G1/hermes_hook.py"

Reads JSON event from stdin, injects routing context before every LLM call,
records outcomes after tasks.
"""
import sys, json, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness_g1 import hook_main

if __name__ == "__main__":
    hook_main()
