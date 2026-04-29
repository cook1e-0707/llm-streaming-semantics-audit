# Phase 3 Mock Safety-Signal Harness

This harness validates safety-signal event recording without using real unsafe
prompts or provider APIs.

## Purpose

Before P3.M2 can run real safety-signal pilots, the repository must prove that
it can represent:

- delayed safety annotations
- terminal refusals
- terminal content filters
- validation watermarks
- redacted visible spans
- client repair actions

The mock harness uses synthetic, redacted traces only. It does not authorize
real safety calls.

## Scenarios

```text
streaming_delayed_annotation
streaming_terminal_refusal
streaming_content_filter
```

Each scenario emits normalized `StreamEvent` objects and writes redacted JSONL,
summary JSON, and aggregate metrics under ignored `artifacts/`.

## Command

```bash
python scripts/run_mock_safety_pilot.py --all
python scripts/check_p3_mock_safety_ready.py
```

## Boundary

The mock harness may compute metrics such as `TTFSS_ms`,
`validation_lag_chars`, and `exposure_window_ms` from explicit synthetic range
labels. It must not infer safety labels from raw text and must not store raw
unsafe prompts.
