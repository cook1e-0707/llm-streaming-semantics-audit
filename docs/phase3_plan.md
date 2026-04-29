# Phase 3 Safety-Signal Pilot Plan

Phase 3 studies safety-signal timing only after benign raw-provider lifecycle
traces are stable. It must not begin with jailbreak datasets or raw unsafe
prompt imports.

## Goal

Measure how provider-visible, SDK-visible, application-visible, and
user-visible events expose safety-relevant timing:

- first safety signal
- validation watermark
- delayed annotation
- refusal signal
- content-filter terminal reason
- retroactive invalidation
- client repair burden

## Phase 3 Milestones

### P3.M1 Redacted Prompt Policy

Define governance for safety-category prompts without committing raw unsafe
text. This milestone may create schemas, policy documents, mock traces, and
redacted placeholders.

### P3.M2 Safety-Signal Timing Traces

Run small, reviewed, provider-level safety-signal pilots only after P3.M1
criteria are satisfied. This milestone remains blocked until prompt sourcing,
review, redaction, output retention, and stop conditions are documented.

### P3.M2a Mock Safety-Signal Harness

Validate safety-signal event ordering, redacted trace persistence, TTFSS, and
range-label metrics using synthetic mock traces only. This does not authorize
real safety-signal provider calls.

### P3.M2b External Safety Prompt Source

Configure the legacy safety prompt directory as an external controlled source.
The repository records only inventory metadata and redacted run plans; raw
unsafe prompt text remains outside git.

### P3.M3 Exposure-Window Metrics

Compute exposure-window and validation-lag metrics only after traces include
validated spans, user-visible boundaries, and safety-signal labels.

## Allowed Now

- Policy and governance documents
- Redacted prompt metadata schemas
- Mock safety-signal traces
- Validator rules for safety-signal event order
- Aggregate-only reporting templates

## Still Forbidden

- Raw unsafe prompt text in git
- Jailbreak benchmark imports
- Real safety-signal API calls
- Provider ranking by strictness
- Full raw provider payload retention
- Framework propagation experiments

## P3.M2 Entry Criteria

Before running real safety-signal pilots, the repository must have:

- a redacted prompt policy
- a reviewed safety-category registry schema
- an approved prompt storage location outside git
- a rule for retaining only aggregate metrics and redacted traces
- provider-specific stop conditions
- explicit command-line network opt-in
- tests proving unsafe prompt text is not committed
- a passing Phase 3 quality gate:

```bash
python scripts/check_phase3_ready.py
python scripts/check_p3_mock_safety_ready.py
python scripts/check_p3_safety_pilot_ready.py
```
