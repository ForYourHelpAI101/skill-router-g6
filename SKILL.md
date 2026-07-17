---
name: skill-router-g1
description: G5 research-optimized skill router — InF-IR expansion, Sinkhorn OT matching, DPP diversity, Thompson sampling, ε-auction, category diversity. Picks the best skills for any task.
version: G5
---

# Skill-Router G1 (G5)

Research-optimized skill selection using 7 papers, 6 algorithmic improvements.

## Location
```
C:\Skill-Router G1\
├── harness.py           v1: keyword matching MVP
├── harness_g1.py → g4   Generations 1-4
├── harness_hybrid.py    Hybrid: keyword + semantic
├── harness_unified.py   G4.5: LLM expand + auction + greedy
├── harness_g5.py        G5: Research-optimized (CURRENT)
```

## G5 Improvements (from 7 papers)

| # | Feature | Paper | Math |
|---|---|---|---|
| 1 | InF-IR Instruction-Aware Expansion | Zhuang 2025 | Domain-aware keyword generation |
| 2 | Sinkhorn Optimal Transport | Cuturi 2013 | K=exp(-C/ε), Sinkhorn iterations |
| 3 | DPP Diversity Penalty | Kulesza 2012 | det(L_S) for diverse subsets |
| 4 | Thompson Sampling | Agrawal 2013 | θ~Beta(α,β) exploration |
| 5 | ε-Auction Selection | Bertsekas 1979 | Price-updating assignment |
| 6 | Category Diversity Enforcer | Ahmadi 2019 | Multi-attribute spread constraint |

## Usage

```bash
cd "C:\Skill-Router G1"
python harness_g5.py "deploy kubernetes to azure with monitoring"
python harness_g5.py --bench
python harness_g5.py --stats
```

## How It Works (G5)

```
Task → [Cache?] → [InF-IR Expand] → [Keyword Pool + Sinkhorn]
                                            ↓
                              [Thompson Sample | DPP-Greedy | ε-Auction]
                                            ↓
                              [Category Diversity Enforcer]
                                            ↓
                                    [K Diverse Skills]
```
