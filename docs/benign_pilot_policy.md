# Benign Pilot Policy

Phase 2 pilot traces are benign-only. The pilot exists to test trace collection,
not to test safety policies.

## Allowed Prompt Categories

- Short text generation
- Long harmless text generation
- Structured JSON generation
- Numbered list generation
- Summarization of user-provided benign text

## Forbidden Prompt Categories

- Unsafe, harmful, or policy-triggering prompts
- Jailbreaks or prompt-injection examples
- Borderline safety content
- Benchmark prompt datasets
- Secrets, credentials, private user data, or proprietary text
- Legacy project prompt files unless separately reviewed and redacted

## Data Retention Policy

Pilot artifacts must be written under ignored directories such as
`artifacts/mock_pilot/` or a future `artifacts/real_pilot/`. Raw result dumps,
large traces, and prompt datasets must not be committed.

## Redaction Policy

Trace records should store payload summaries and redacted payload metadata by
default. Full raw provider outputs are not required for Phase 2 harness
validation.

## Cost-Control Policy

P2.M1 has no provider cost because it uses only mock providers. Future real API
pilots must default to dry-run mode, use small output limits, require explicit
network opt-in, and enforce conservative maximum call counts.

## Phase Boundary

Phase 2 cannot use unsafe prompts, jailbreak datasets, or safety-signal
workloads. Those belong to later phases after a separate ethical and data review.
