# LLM Streaming Semantics Audit

This repository studies runtime safety semantics in streaming and non-streaming
LLM APIs. The focus is release timing, validation timing, visibility,
safety-signal propagation, refusal handling, settlement, and agent action
commitment.

The project does not treat `stream=True` and `stream=False` as a sufficient
binary framing. A provider can stream immediately, stream through a moderation
buffer, emit delayed annotations, refuse at a terminal boundary, or expose
different semantics through an SDK or framework. The audit therefore separates
provider wire-visible events, SDK-visible events, application-visible events,
user-visible events, and agent action-commit events.

## Core Question

When is streamed LLM output actually safe to reveal, persist, or use for
downstream actions?

## Boundary Model

- Release: when content is emitted from one layer to the next.
- Validation: when a layer marks content or a span as checked, filtered,
  refused, or otherwise safety-relevant.
- Visibility: when content becomes visible to a user, persistent log,
  downstream component, or tool.
- Settlement: when a layer considers the trace complete and no more repair or
  safety events are expected.
- Action commit: when an agent or application commits an external side effect
  based on generated content.

## Current Phase

Phase 0 is complete: the repository has the research contract, shared
terminology, trace schema, initial metrics, README generation, provider audit
templates, and legacy inventory.

Phase 1 is complete: the provider documentation evidence registry, generated
provider matrix, unknown-field review, and readiness quality gate are in place.
The next allowed phase is Phase 2, limited to a benign-only raw API pilot.

## Project Progress

Progress is tracked in `docs/project_progress.toml` and rendered into this
README by `python scripts/update_readme_status.py`.

<!-- PROJECT_PROGRESS_START -->
```text
Legend: [done] complete, [in_progress] active, [next] immediate next, [planned] queued, [deferred] later
Current phase: P2
Next milestone: P2.M1

|-- [done] P0 Research Contract and Measurement Schema
|   |-- [done] P0.M1 Repository scaffold
|   |-- [done] P0.M2 Semantics taxonomy
|   |-- [done] P0.M3 Trace event and metric schema
|   |-- [done] P0.M4 README status generation
|   `-- [done] P0.M5 Legacy project inventory
|-- [done] P1 Provider Documentation Audit
|   |-- [done] P1.M1 Source note templates
|   |-- [done] P1.M2 Official source evidence collection
|   |-- [done] P1.M3 Provider matrix evidence validation
|   |-- [done] P1.M4 Open questions and unknown-field review
|   `-- [done] P1.M5 Phase 1 readiness quality gate
|-- [next] P2 Raw API Benign Pilot
|   |-- [next] P2.M1 Provider adapter interface
|   |-- [planned] P2.M2 Benign streaming trace collection
|   `-- [planned] P2.M3 Trace quality checks
|-- [deferred] P3 Safety-Signal Pilot
|   |-- [planned] P3.M1 Redacted prompt policy
|   |-- [planned] P3.M2 Safety signal timing traces
|   `-- [planned] P3.M3 Exposure-window metrics
`-- [deferred] P4 Agent Framework Propagation
    |-- [planned] P4.M1 Framework instrumentation plan
    |-- [planned] P4.M2 Action-commit boundary traces
    `-- [planned] P4.M3 Provider-vs-framework propagation analysis
```
<!-- PROJECT_PROGRESS_END -->

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
- Machine-readable metrics registry: `docs/metrics_registry.yaml`
- Machine-readable project progress: `docs/project_progress.toml`
- Machine-readable provider evidence: `docs/provider_evidence.yaml`
- Provider documentation matrix: `docs/provider_matrix.md`
- Phase 1 unknown-field review: `docs/phase1_unknown_fields_review.md`
- Phase 1 readiness gate: `docs/phase1_quality_gate.md`
- Experiment scope: `docs/experiment_scope.md`
- Legacy project notes: `docs/legacy_project_notes.md`

## Project Tree

<!-- PROJECT_TREE_START -->
```text
llm-streaming-semantics-audit/
|-- docs/
|   |-- source_notes/
|   |   |-- anthropic.md
|   |   |-- aws_bedrock.md
|   |   |-- azure_openai.md
|   |   |-- google_vertex_gemini.md
|   |   |-- openai_agents_sdk.md
|   |   |-- openai_guardrails.md
|   |   `-- README.md
|   |-- experiment_scope.md
|   |-- legacy_project_notes.md
|   |-- metrics.md
|   |-- metrics_registry.yaml
|   |-- phase1_quality_gate.md
|   |-- phase1_unknown_fields_review.md
|   |-- project_progress.toml
|   |-- provider_evidence.yaml
|   |-- provider_matrix.md
|   |-- research_charter.md
|   `-- semantics_taxonomy.md
|-- scripts/
|   |-- check_phase1_ready.py
|   |-- generate_provider_matrix.py
|   |-- provider_evidence.py
|   |-- update_readme_status.py
|   `-- validate_provider_matrix.py
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
|   |-- test_phase1_quality_gate.py
|   |-- test_provider_matrix.py
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
| Metric | Status | Layers | Definition |
| --- | --- | --- | --- |
| `TTFB_ms` | implemented | `provider`, `sdk` | elapsed milliseconds from request_start to first_byte |
| `TTFT_ms` | implemented | `provider`, `sdk`, `framework`, `application`, `user_visible` | elapsed milliseconds from request_start to first_token |
| `TTFSS_ms` | implemented | `provider`, `sdk`, `framework`, `application` | elapsed milliseconds from request_start to the first safety-relevant signal |
| `validation_lag_chars` | stub | `provider`, `sdk`, `framework`, `application`, `user_visible` | emitted characters beyond the latest validation watermark at safety-signal time |
| `validation_lag_tokens` | stub | `provider`, `sdk`, `framework`, `application`, `user_visible` | emitted tokens beyond the latest validation watermark at safety-signal time |
| `exposure_window_chars` | stub | `application`, `user_visible` | characters visible before a later safety signal or invalidation covered them |
| `exposure_window_tokens` | stub | `application`, `user_visible` | tokens visible before a later safety signal or invalidation covered them |
| `exposure_window_ms` | stub | `application`, `user_visible` | elapsed milliseconds between first visibility and later safety signal or repair |
| `retroactive_invalidation` | stub | `provider`, `sdk`, `framework`, `application`, `user_visible` | whether a later event invalidated content already emitted downstream |
| `terminal_reason_consistency` | stub | `provider`, `sdk`, `framework`, `application`, `user_visible` | whether terminal reasons agree across observable layers for one trace |
| `settlement_lag_ms` | implemented | `provider`, `sdk`, `framework`, `application` | elapsed milliseconds between the last terminal output event and settled |
| `client_repair_burden` | stub | `application`, `user_visible` | client-side repair actions needed after delayed safety, refusal, filtering, or invalidation |
<!-- METRICS_REGISTRY_END -->

## Safety and Data Policy

This repository must not contain API keys, raw unsafe prompts, private provider
credentials, or large raw result dumps. Redacted fixtures and aggregate metrics
are preferred.
