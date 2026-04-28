# Experiment Scope

## Phase 0: Research Contract and Measurement Schema

Phase 0 defines the research question, terminology, provider documentation audit
template, trace schema, and initial metrics. It intentionally avoids provider
API calls and raw safety experiments.

## Phase 1: Provider Documentation Audit

Phase 1 records official documentation evidence in source notes and maps those
claims to the semantics taxonomy. Unsupported behavior remains `unknown` or
`TODO(source needed)`.

## Phase 2: Raw API Benign Pilot

Phase 2 collects benign traces to validate event ordering, timestamps, transport
behavior, and status generation. The goal is harness validation, not safety
measurement.

## Phase 3: Safety-Signal Pilot

Phase 3 introduces reviewed and redacted safety categories only after the trace
schema, data policy, and ethical handling rules are stable.

## Phase 4: Agent Framework Propagation

Phase 4 studies how frameworks propagate or transform provider-level semantics.
Framework traces are not treated as provider ground truth.

## Exclusions

- Unsafe raw prompts in the repository
- Secrets, credentials, or local key files
- Large raw result dumps
- Provider adapters before the schema is stable
- Claims about provider behavior without source notes or traces
