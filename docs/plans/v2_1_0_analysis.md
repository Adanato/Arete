# Technical Debt Analysis — v2.1.0 Baseline

This report details the status of the `v2.1` branch after enabling strict architectural and complexity guardrails.

---

## 1. Architectural Health (Import Linter) 🏗️
**Status: EXCELLENT (0 Violations)**

Our **Domain-Driven Design (DDD)** layers are perfectly isolated. 
- [x] **Domain Purity**: The core `domain` package has zero dependencies on other layers.
- [x] **Dependency Inversion**: `application` logic communicates with `infrastructure` only through abstract interfaces.

## 2. Complexity Heatmap (McCabe C901) 🌡️
**Status: AT RISK (18 High-Complexity Functions)**

We have several "God Functions" that act as gravity wells for technical debt. The following are the top targets for refactoring in v2.1:

| Module | Function | Score (Limit: 10) | Risk Level |
| :--- | :--- | :--- | :--- |
| `interface/cli.py` | `migrate` | **38** | 🔴 Critical |
| `interface/cli.py` | `check_file` | **35** | 🔴 Critical |
| `application/pipeline.py` | `run_pipeline` | **25** | 🟠 High |
| `application/vault_service.py` | `apply_updates` | **21** | 🟠 High |
| `infrastructure/anki_connect.py` | `_sync_single_note` | **21** | 🟠 High |
| `application/parser.py` | `parse_file` | **20** | 🟠 High |
| `application/graph_resolver.py` | `build_graph` | **19** | 🟠 High |

## 3. Documentation & Standards (Ruff D-Series) 📖
**Status: NEEDS REFACTOR (111 Minor Errors)**

The codebase has significant inconsistency in documentation formatting, which will hinder external contributors.
- **Missing Docstrings**: Many magic methods (`__init__`, `__enter__`) lack documentation.
- **Formatting**: ~80% of docstrings fail the "imperative mood" or "blank line" rules.
- **TODOs**: Several unresolved `TODO` comments discovered in `infrastructure`.

---

## v2.1 Recommendation
I recommend focusing Milestone 1 specifically on **decoupling the CLI**. Moving the logic out of `cli.py` into separate command modules will immediately resolve our two biggest complexity spikes (Score 38 and 35).
