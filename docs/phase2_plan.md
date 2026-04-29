# Phase 2 Plan

Phase 2 validates the trace harness with benign workloads before any
safety-signal experiment. The goal is to prove that the project can capture,
normalize, record, and validate streaming and non-streaming runtime events.

## Why Mock Traces Come First

Real provider traces mix provider behavior, SDK behavior, network timing, client
bugs, and schema design. P2.M1 removes those variables by using deterministic
mock traces. If the recorder and validator cannot handle controlled traces, real
API traces would not be interpretable.

## P2.M1 Includes

- Provider-neutral adapter contract
- Deterministic mock provider
- Trace recorder
- Trace event-order validator
- Benign prompt registry
- Mock pilot script
- Phase 2 readiness gate

## P2.M1 Forbids

- Real provider API calls
- Real OpenAI, Anthropic, Azure, AWS, Google, DeepSeek, OpenRouter, or other
  provider adapters
- Unsafe prompts
- Benchmark prompt imports
- Legacy project code or result migration
- Framework propagation studies

## P2.M2 Preview

After the Phase 2 readiness gate passes, P2.M2 may add a small-scale real
provider pilot. That pilot must remain benign-only, default to dry-run mode, and
require explicit opt-in for network calls.

## Benign-Only Rule

Phase 2 measures harness behavior, not safety behavior. Prompts must be short,
harmless, and easy to inspect. Safety-signal workloads, jailbreaks, and
benchmark prompt datasets remain out of scope until a later phase with a
separate data policy.
