# AGENTS.md

This repository is a research codebase for studying streaming and non-streaming
LLM API semantics.

## Project Goal

Build a rigorous, reproducible black-box audit framework for release,
validation, visibility, refusal, settlement, and action-commit semantics in LLM
APIs and agent frameworks.

## Non-negotiable Constraints

- Do not commit secrets, `.env`, credentials, API keys, or local key files.
- Do not copy raw data or large results from the legacy project.
- Do not run provider API calls unless explicitly requested.
- Do not fabricate provider behavior. If a provider behavior is not backed by a
  source or trace, mark it as TODO or unknown.
- Keep raw provider, SDK, and framework layers separate.
- Prefer small, testable increments.
- Every schema change must have tests.
- Every metric must have a definition in `docs/metrics.md`.

## Development Commands

Use these commands when available:

```bash
python -m pytest
python scripts/update_readme_status.py --check
```

## Research Invariants

The project distinguishes:

1. Provider wire-visible events
2. SDK-visible events
3. Application-visible events
4. User-visible events
5. Agent action-commit events

Do not collapse these layers.
