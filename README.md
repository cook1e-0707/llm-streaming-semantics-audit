# LLM Streaming Semantics Audit

This repository studies runtime safety semantics in streaming and non-streaming
LLM APIs. The focus is release timing, validation timing, safety-signal
propagation, refusal handling, settlement, and agent action commitment.

The project does not treat `stream=True` and `stream=False` as a sufficient
binary framing. It separates provider wire-visible events, SDK-visible events,
application-visible events, user-visible events, and agent action-commit events.

## Core Question

When is streamed LLM output actually safe to reveal, persist, or use for
downstream actions?

## Current Phase

Phase 0 defines the research contract, shared terminology, trace schema, and
initial metrics. Provider adapters and external API calls are intentionally out
of scope for this phase.

## Scope

Initial scope:

- Raw commercial provider API behavior
- Streaming and non-streaming response traces
- Safety-signal timing
- Refusal and filtering semantics
- Agent framework propagation of provider-level semantics

Out of scope for the initial phase:

- Training a new moderation model
- Ranking providers by policy strictness
- Publishing unsafe prompt text
- Committing raw secrets, large datasets, or full provider outputs

## Documents

- Research charter: `docs/research_charter.md`
- Semantics taxonomy: `docs/semantics_taxonomy.md`
- Metrics definitions: `docs/metrics.md`
- Provider documentation matrix: `docs/provider_matrix.md`
- Experiment scope: `docs/experiment_scope.md`
- Legacy project notes: `docs/legacy_project_notes.md`

## Project Tree

<!-- PROJECT_TREE_START -->
```text
llm-streaming-semantics-audit/
|-- docs/
|   |-- experiment_scope.md
|   |-- legacy_project_notes.md
|   |-- metrics.md
|   |-- provider_matrix.md
|   |-- research_charter.md
|   `-- semantics_taxonomy.md
|-- scripts/
|   `-- update_readme_status.py
|-- src/
|   `-- lssa/
|       |-- schema/
|       |   |-- __init__.py
|       |   |-- events.py
|       |   `-- metrics.py
|       |-- utils/
|       |   |-- __init__.py
|       |   `-- time.py
|       `-- __init__.py
|-- tests/
|   |-- test_event_schema.py
|   `-- test_readme_status.py
|-- .env.example
|-- .gitignore
|-- AGENTS.md
|-- LICENSE
|-- pyproject.toml
`-- README.md
```
<!-- PROJECT_TREE_END -->

## Metrics Registry

<!-- METRICS_REGISTRY_START -->
| Metric | Status | Definition |
| --- | --- | --- |
| `TTFB_ms` | implemented | elapsed milliseconds from `request_start` to `first_byte`. |
| `TTFT_ms` | implemented | elapsed milliseconds from `request_start` to `first_token`. |
| `TTFSS_ms` | implemented | elapsed milliseconds from `request_start` to the first safety-relevant signal. |
| `validation_lag_chars` | stub | emitted characters beyond the latest validation watermark at the time a safety signal is observed. |
| `validation_lag_tokens` | stub | emitted tokens beyond the latest validation watermark at the time a safety signal is observed. |
| `exposure_window_chars` | stub | number of characters that were visible before a later safety signal or invalidation covered them. |
| `exposure_window_tokens` | stub | number of tokens that were visible before a later safety signal or invalidation covered them. |
| `exposure_window_ms` | stub | elapsed milliseconds between first visibility of later-invalidated content and the safety signal or repair event. |
| `retroactive_invalidation` | stub | boolean indicator that a later event invalidated, filtered, or refused content already emitted to a downstream layer. |
| `terminal_reason_consistency` | stub | whether terminal reasons agree across provider, SDK, framework, application, and user-visible layers for one trace. |
| `settlement_lag_ms` | implemented | elapsed milliseconds between the last terminal output event and `settled`. |
| `client_repair_burden` | stub | count or structured score of client-side actions needed after delayed safety, refusal, filtering, or invalidation. |
<!-- METRICS_REGISTRY_END -->

## Safety and Data Policy

This repository must not contain API keys, raw unsafe prompts, private provider
credentials, or large raw result dumps. Redacted fixtures and aggregate metrics
are preferred.
