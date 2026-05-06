# Xiaomi MiMo OpenAI-Compatible Benign Pilot Summary

This report summarizes the latest redacted trace for each benign prompt
and response mode under `artifacts/xiaomi_mimo_smoke/xiaomi_mimo_openai`.

## Status

- Phase: P2 real benign pilot result consolidation
- Provider: `xiaomi_mimo_openai`
- Latest trace start: `2026-05-06T02:13:12.931878+00:00`
- Trace validity: `yes`
- Content fields redacted: `yes`
- Provider API calls in this report: historical local artifacts only; this
  script does not call provider APIs.

## Scope Boundary

These traces use benign prompts only and validate harness behavior. They do
not support claims about provider safety, refusal behavior, or harmful-content
exposure windows.

## Latest Trace Summary

| Prompt | Mode | Model | Valid | Events | Chunks | Final chars | Output tokens | Total tokens | TTFB ms | TTFT ms | Settlement lag ms | Terminal reason | Provider stop reason |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `short_text_generation` | `streaming` | `mimo-v2-omni` | yes | 9 | 1 | n/a | n/a | n/a | 3330.363 | 3330.391 | 0.044 | `length` | `length` |
| `short_text_generation` | `nonstreaming` | `mimo-v2-omni` | yes | 6 | 0 | n/a | 16 | 276 | 0.033 | n/a | 0.008 | `length` | `length` |

## Notes

- `TTFB_ms` is measured from normalized `request_start` to `first_byte`.
- `TTFT_ms` is only defined for streaming traces that emit `first_token`.
- `Final chars` uses normalized character counts and does not require
  retaining model text.
- `Output tokens` and `Total tokens` use provider-reported usage when
  exposed by the adapter; they are not inferred from redacted text.
- `Provider stop reason` is copied from provider metadata when exposed by
  the adapter; otherwise it is reported as `unknown`.
- Artifacts remain under ignored local directories and are not committed.
