# Legacy Project Notes

## Legacy Path

`/Users/guanjie/Documents/llm_api/streaming_or_not/streaming-vs-nonstreaming`

## Status

The legacy project is a prior experiment codebase for comparing streaming and
non-streaming LLM API behavior. It remains useful as a historical baseline and
possible source of concepts, but it is not the source of truth for this new
repository.

## Inspection Scope

Inventory was limited to safe path and filename inspection. The inventory did
not read `.env`, `keys/`, `.venv/`, `results/`, `results_chimera/`, `logs/`, or
large result contents. Dataset directories were treated as non-migratable unless
a later data policy explicitly approves redacted fixtures.

## High-Level Structure Observed

- `README.md`, `.gitignore`, `.env.example`, `requirements.txt`
- `configs/`: experiment and model configuration filenames
- `docs/`: schema, analysis, annotation, and fake-streaming notes
- `scripts/`: batch collection, probing, normalization, and analysis scripts
- `src/`: adapters, runners, metrics, analysis, judges, utilities, data helpers,
  annotations, gateway, and recollection modules
- `tests/`: tests for pipelines, derived metrics, reports, annotations, and
  recollection
- `data/`: benchmark and safety dataset filenames; contents were not inspected
- local output or sensitive directories present but excluded from inventory:
  `.env`, `.venv/`, `results/`, `results_chimera/`, `logs/`

## Source and Documentation Areas Observed

Potential code areas by filename:

- `src/adapters/`: `base.py`, `openai_adapter.py`, `anthropic_adapter.py`,
  `deepseek_adapter.py`
- `src/runners/`: performance, safety, annotation, sharded, and recollection
  runners
- `src/metrics/`: request metrics and derived metric builders
- `src/judges/`: refusal, interruption, moderation, and prefix-exposure rules
- `src/utils/`: retry, tokenizer, time, I/O, results layout, and SSE helpers
- `src/analysis/`: aggregation, plotting, and report builders
- `src/data/`: benchmark and experiment prompt-file builders
- `src/gateway/`: gateway application entry point
- `src/annotations/`: span annotation utilities
- `src/recollection/`: wave 2 recollection planning utilities

Documentation areas by filename:

- `docs/event_log_schema.md`
- `docs/gateway_trace_schema.md`
- `docs/analysis_plan.md`
- `docs/annotation_rubric.md`
- `docs/qc_checklist.md`
- `docs/v2_compatibility_audit.md`
- `docs/fake_streaming_experiment.md`
- `docs/fake_streaming_live_validation.md`
- `docs/run_whitebox_fake_streaming.md`

## Potentially Reusable Components

- Provider adapter concepts, after separating provider, SDK, framework,
  application, and user-visible event layers
- SSE parsing utilities, after verifying they preserve raw provider events and
  timestamps needed by the new schema
- Time and I/O helpers, after checking that they do not encode old result paths
  or old metric assumptions
- Metric names and derived-metric ideas, after semantic redefinition in
  `docs/metrics.md`
- Event-log and gateway trace schema ideas, after compatibility review against
  `src/lssa/schema/events.py`
- Existing tests as examples of pipeline risks, not as direct fixtures

## Components That Must Not Be Copied

- `.env` files
- `keys/`
- `.venv/`
- `results/`
- `results_chimera/`
- `logs/`
- `data/raw/`
- `data/safety/`
- large raw provider outputs
- raw unsafe prompt text
- full benchmark prompt datasets
- local result layouts that assume the legacy experiment framing

## Conceptual Mismatch

The legacy project frames the question as streaming versus non-streaming
behavior. The new project frames the question as runtime safety semantics across
release, validation, visibility, refusal, settlement, and action-commit
boundaries. Code should not be migrated until it can preserve those boundaries.

Specific mismatch risks:

- Legacy adapters may collapse provider wire events into application metrics.
- Legacy metrics may measure latency or refusal behavior without explicit
  validation and visibility boundaries.
- Legacy result paths may assume raw outputs are stored in-repo or near-repo.
- Legacy safety datasets may contain raw prompts that are not allowed in this
  repository.
- Legacy reports may compare providers before the documentation matrix defines
  comparable semantics.

## Migration Policy

- Migrate concepts before code.
- Migrate schema only after reviewing compatibility.
- Migrate provider adapters only after the new trace schema is stable.
- Never migrate raw results into the repo.
- Never migrate secrets or environment files.
- Never migrate prompt datasets or safety examples without a written data policy
  and redaction review.
- Prefer new tests that encode the new semantics rather than importing old test
  fixtures.
