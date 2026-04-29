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
Phase 2 is complete: the repository has a provider-neutral mock trace harness,
redacted benign pilot summaries for OpenAI Responses, Anthropic Messages, and
AWS Bedrock Converse, a cross-provider benign lifecycle comparison, and a
dry-run scaled benign batch runner. Phase 3 has started at the policy and mock
safety-signal layer. The legacy safety prompt directory is configured only as
an external source; real safety-signal timing runs require guarded opt-in,
reviewed source status, and redacted outputs.

## Project Progress

Progress is tracked in `docs/project_progress.toml` and rendered into this
README by `python scripts/update_readme_status.py`.

<!-- PROJECT_PROGRESS_START -->
```text
Legend: [done] complete, [in_progress] active, [next] immediate next, [planned] queued, [deferred] later
Current phase: P3
Next milestone: P3.M2

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
|-- [done] P2 Raw API Benign Pilot
|   |-- [done] P2.M1 Provider adapter interface
|   |-- [done] P2.M2 OpenAI benign pilot and summary
|   |-- [done] P2.M3 Anthropic and Bedrock benign adapters
|   |-- [done] P2.M4 Benign lifecycle comparison
|   |-- [done] P2.M5 Scaled benign batch runner
|   `-- [done] P2.M6 Stop-reason probe manifest
|-- [in_progress] P3 Safety-Signal Pilot
|   |-- [done] P3.M1 Redacted prompt policy
|   |-- [done] P3.M2a Mock safety-signal harness
|   |-- [done] P3.M2b External safety prompt source
|   |-- [next] P3.M2 Safety signal timing traces
|   |-- [planned] P3.M3 Exposure-window metrics
|   `-- [done] P3.M4 LLM-as-a-judge dual NVIDIA adjudication
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
- Phase 2 plan: `docs/phase2_plan.md`
- Phase 2 real pilot plan: `docs/phase2_real_pilot_plan.md`
- Scaled benign experiment plan: `docs/scaled_benign_experiment_plan.md`
- Benign batch manifest example: `docs/benign_experiment_manifest.example.toml`
- Stop reason probe plan: `docs/stop_reason_probe_plan.md`
- Stop reason probe manifest example: `docs/stop_reason_probe_manifest.example.toml`
- AWS Bedrock SDK configuration: `docs/bedrock_sdk_config.md`
- OpenAI benign pilot summary: `docs/pilot_runs/openai_responses_benign_pilot.md`
- Anthropic benign pilot summary: `docs/pilot_runs/anthropic_messages_benign_pilot.md`
- AWS Bedrock benign pilot summary: `docs/pilot_runs/aws_bedrock_converse_benign_pilot.md`
- Benign lifecycle comparison: `docs/pilot_runs/benign_lifecycle_comparison.md`
- Phase 3 plan: `docs/phase3_plan.md`
- Phase 3 quality gate: `docs/phase3_quality_gate.md`
- Phase 3 mock safety harness: `docs/phase3_mock_safety_harness.md`
- External safety prompt source: `docs/external_safety_prompt_source.md`
- Phase 3 safety pilot plan: `docs/phase3_safety_pilot_plan.md`
- Optional judge adjudication plan: `docs/judge_adjudication_plan.md`
- Safety prompt policy: `docs/safety_prompt_policy.md`
- Redacted safety prompt registry example: `docs/safety_prompt_registry.example.yaml`
- Trace contract: `docs/trace_contract.md`
- Benign pilot policy: `docs/benign_pilot_policy.md`
- Real API data policy: `docs/real_api_data_policy.md`
- Experiment scope: `docs/experiment_scope.md`
- Legacy project notes: `docs/legacy_project_notes.md`

## Project Tree

<!-- PROJECT_TREE_START -->
```text
llm-streaming-semantics-audit/
|-- docs/
|   |-- pilot_runs/
|   |   |-- anthropic_messages_benign_pilot.md
|   |   |-- aws_bedrock_converse_benign_pilot.md
|   |   |-- benign_lifecycle_comparison.md
|   |   `-- openai_responses_benign_pilot.md
|   |-- source_notes/
|   |   |-- anthropic.md
|   |   |-- aws_bedrock.md
|   |   |-- azure_openai.md
|   |   |-- google_vertex_gemini.md
|   |   |-- openai_agents_sdk.md
|   |   |-- openai_guardrails.md
|   |   `-- README.md
|   |-- bedrock_sdk_config.md
|   |-- benign_experiment_manifest.example.toml
|   |-- benign_pilot_policy.md
|   |-- experiment_scope.md
|   |-- external_safety_prompt_source.md
|   |-- judge_adjudication_plan.md
|   |-- legacy_project_notes.md
|   |-- metrics.md
|   |-- metrics_registry.yaml
|   |-- p3_overnight_batch.md
|   |-- phase1_quality_gate.md
|   |-- phase1_unknown_fields_review.md
|   |-- phase2_plan.md
|   |-- phase2_real_pilot_plan.md
|   |-- phase3_mock_safety_harness.md
|   |-- phase3_plan.md
|   |-- phase3_quality_gate.md
|   |-- phase3_safety_pilot_plan.md
|   |-- project_progress.toml
|   |-- provider_evidence.yaml
|   |-- provider_matrix.md
|   |-- real_api_data_policy.md
|   |-- research_charter.md
|   |-- safety_prompt_policy.md
|   |-- safety_prompt_registry.example.yaml
|   |-- scaled_benign_experiment_plan.md
|   |-- semantics_taxonomy.md
|   |-- stop_reason_probe_manifest.example.toml
|   |-- stop_reason_probe_plan.md
|   `-- trace_contract.md
|-- scripts/
|   |-- check_judge_ready.py
|   |-- check_p3_mock_safety_ready.py
|   |-- check_p3_safety_pilot_ready.py
|   |-- check_phase1_ready.py
|   |-- check_phase2_pilot_ready.py
|   |-- check_phase3_ready.py
|   |-- check_scaled_benign_ready.py
|   |-- compare_benign_lifecycle.py
|   |-- generate_provider_matrix.py
|   |-- inspect_external_safety_prompts.py
|   |-- provider_evidence.py
|   |-- run_benign_batch.py
|   |-- run_judge_adjudication.py
|   |-- run_mock_pilot.py
|   |-- run_mock_safety_pilot.py
|   |-- run_p3_overnight_batch.py
|   |-- run_real_benign_pilot.py
|   |-- run_safety_signal_pilot.py
|   |-- summarize_real_pilot.py
|   |-- update_readme_status.py
|   `-- validate_provider_matrix.py
|-- src/
|   `-- lssa/
|       |-- adapters/
|       |   |-- __init__.py
|       |   |-- anthropic_messages.py
|       |   |-- aws_bedrock_converse.py
|       |   |-- base.py
|       |   |-- mock.py
|       |   `-- openai_responses.py
|       |-- experiments/
|       |   |-- __init__.py
|       |   `-- manifest.py
|       |-- judging/
|       |   |-- __init__.py
|       |   `-- nvidia.py
|       |-- prompts/
|       |   |-- benign_prompts.yaml
|       |   `-- safety_external.py
|       |-- schema/
|       |   |-- __init__.py
|       |   |-- events.py
|       |   `-- metrics.py
|       |-- tracing/
|       |   |-- __init__.py
|       |   |-- fixtures.py
|       |   |-- recorder.py
|       |   |-- safety_fixtures.py
|       |   `-- validator.py
|       |-- utils/
|       |   |-- __init__.py
|       |   |-- aws_bedrock.py
|       |   `-- time.py
|       `-- __init__.py
|-- tests/
|   |-- test_adapter_contract.py
|   |-- test_anthropic_messages.py
|   |-- test_aws_bedrock_config.py
|   |-- test_aws_bedrock_converse.py
|   |-- test_benign_batch.py
|   |-- test_benign_lifecycle_comparison.py
|   |-- test_event_schema.py
|   |-- test_external_safety_prompts.py
|   |-- test_mock_provider.py
|   |-- test_mock_safety_pilot.py
|   |-- test_nvidia_judge.py
|   |-- test_p3_overnight_batch.py
|   |-- test_phase1_quality_gate.py
|   |-- test_phase2_pilot_ready.py
|   |-- test_phase3_quality_gate.py
|   |-- test_provider_matrix.py
|   |-- test_readme_status.py
|   |-- test_real_benign_pilot.py
|   |-- test_real_pilot_summary.py
|   |-- test_trace_recorder.py
|   `-- test_trace_validator.py
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
| `validation_lag_chars` | implemented | `provider`, `sdk`, `framework`, `application`, `user_visible` | emitted characters beyond the latest validation watermark at safety-signal time |
| `validation_lag_tokens` | implemented | `provider`, `sdk`, `framework`, `application`, `user_visible` | emitted tokens beyond the latest validation watermark at safety-signal time |
| `exposure_window_chars` | implemented | `application`, `user_visible` | characters visible before a later safety signal or invalidation covered them |
| `exposure_window_tokens` | implemented | `application`, `user_visible` | tokens visible before a later safety signal or invalidation covered them |
| `exposure_window_ms` | implemented | `application`, `user_visible` | elapsed milliseconds between first visibility and later safety signal or repair |
| `retroactive_invalidation` | stub | `provider`, `sdk`, `framework`, `application`, `user_visible` | whether a later event invalidated content already emitted downstream |
| `terminal_reason_consistency` | stub | `provider`, `sdk`, `framework`, `application`, `user_visible` | whether terminal reasons agree across observable layers for one trace |
| `settlement_lag_ms` | implemented | `provider`, `sdk`, `framework`, `application` | elapsed milliseconds between the last terminal output event and settled |
| `client_repair_burden` | stub | `application`, `user_visible` | client-side repair actions needed after delayed safety, refusal, filtering, or invalidation |
<!-- METRICS_REGISTRY_END -->

## Safety and Data Policy

This repository must not contain API keys, raw unsafe prompts, private provider
credentials, or large raw result dumps. Redacted fixtures and aggregate metrics
are preferred.
