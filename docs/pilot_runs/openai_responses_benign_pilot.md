# OpenAI Responses Benign Pilot Summary

This report summarizes the latest redacted trace for each benign prompt
and response mode under `artifacts/real_pilot/openai_responses`.

## Status

- Phase: P2 real benign pilot result consolidation
- Provider: `openai_responses`
- Latest trace start: `2026-04-29T02:37:04.815004+00:00`
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
| `benign_summary` | `streaming` | `gpt-4.1-mini` | yes | 24 | 16 | 98 | n/a | n/a | 836.762 | 2497.404 | 0.008 | `complete` | `unknown` |
| `benign_summary` | `nonstreaming` | `gpt-4.1-mini` | yes | 6 | 0 | 98 | n/a | n/a | 1165.356 | n/a | 0.006 | `complete` | `unknown` |
| `long_text_generation` | `streaming` | `gpt-4.1-mini` | yes | 109 | 101 | 608 | n/a | n/a | 951.109 | 2140.552 | 0.012 | `complete` | `unknown` |
| `long_text_generation` | `nonstreaming` | `gpt-4.1-mini` | yes | 6 | 0 | 608 | n/a | n/a | 2844.857 | n/a | 0.005 | `complete` | `unknown` |
| `numbered_list_generation` | `streaming` | `gpt-4.1-mini` | yes | 136 | 128 | 729 | n/a | n/a | 840.616 | 1018.920 | 0.022 | `complete` | `unknown` |
| `numbered_list_generation` | `nonstreaming` | `gpt-4.1-mini` | yes | 6 | 0 | 707 | n/a | n/a | 3848.149 | n/a | 0.005 | `complete` | `unknown` |
| `short_text_generation` | `streaming` | `gpt-4.1-mini` | yes | 17 | 9 | 58 | n/a | n/a | 2324.892 | 3418.280 | 0.008 | `complete` | `unknown` |
| `short_text_generation` | `nonstreaming` | `gpt-4.1-mini` | yes | 6 | 0 | 58 | n/a | n/a | 1524.352 | n/a | 0.005 | `complete` | `unknown` |
| `structured_json_generation` | `streaming` | `gpt-4.1-mini` | yes | 50 | 42 | 165 | n/a | n/a | 1668.958 | 4359.041 | 0.007 | `complete` | `unknown` |
| `structured_json_generation` | `nonstreaming` | `gpt-4.1-mini` | yes | 6 | 0 | 165 | n/a | n/a | 2995.970 | n/a | 0.005 | `complete` | `unknown` |

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
