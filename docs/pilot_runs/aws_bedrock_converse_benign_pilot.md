# AWS Bedrock Converse Benign Pilot Summary

This report summarizes the latest redacted trace for each benign prompt
and response mode under `artifacts/real_pilot/aws_bedrock_converse`.

## Status

- Phase: P2 real benign pilot result consolidation
- Provider: `aws_bedrock_converse`
- Latest trace start: `2026-04-29T04:54:24.290108+00:00`
- Trace validity: `yes`
- Content fields redacted: `yes`
- Provider API calls in this report: historical local artifacts only; this
  script does not call provider APIs.

## Scope Boundary

These traces use benign prompts only and validate harness behavior. They do
not support claims about provider safety, refusal behavior, or harmful-content
exposure windows.

## Latest Trace Summary

| Prompt | Mode | Model | Valid | Events | Chunks | Final chars | TTFB ms | TTFT ms | Settlement lag ms | Terminal reason | Provider stop reason |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `benign_summary` | `streaming` | `amazon.nova-micro-v1:0` | yes | 15 | 7 | 101 | 2622.055 | 2622.440 | 0.031 | `complete` | `end_turn` |
| `benign_summary` | `nonstreaming` | `amazon.nova-micro-v1:0` | yes | 6 | 0 | 101 | 2588.385 | n/a | 0.007 | `complete` | `end_turn` |
| `long_text_generation` | `streaming` | `amazon.nova-micro-v1:0` | yes | 57 | 49 | 728 | 2665.706 | 2666.085 | 0.034 | `complete` | `end_turn` |
| `long_text_generation` | `nonstreaming` | `amazon.nova-micro-v1:0` | yes | 6 | 0 | 776 | 3090.666 | n/a | 0.026 | `length` | `max_tokens` |
| `numbered_list_generation` | `streaming` | `amazon.nova-micro-v1:0` | yes | 56 | 48 | 567 | 2632.865 | 2633.338 | 0.035 | `length` | `max_tokens` |
| `numbered_list_generation` | `nonstreaming` | `amazon.nova-micro-v1:0` | yes | 6 | 0 | 648 | 2894.504 | n/a | 0.013 | `length` | `max_tokens` |
| `short_text_generation` | `streaming` | `amazon.nova-micro-v1:0` | yes | 15 | 7 | 86 | 2829.576 | 2829.818 | 0.012 | `complete` | `end_turn` |
| `short_text_generation` | `nonstreaming` | `amazon.nova-micro-v1:0` | yes | 6 | 0 | 86 | 2654.433 | n/a | 0.014 | `complete` | `end_turn` |
| `structured_json_generation` | `streaming` | `amazon.nova-micro-v1:0` | yes | 39 | 31 | 419 | 2611.202 | 2611.626 | 0.024 | `complete` | `end_turn` |
| `structured_json_generation` | `nonstreaming` | `amazon.nova-micro-v1:0` | yes | 6 | 0 | 409 | 2880.483 | n/a | 0.015 | `complete` | `end_turn` |

## Notes

- `TTFB_ms` is measured from normalized `request_start` to `first_byte`.
- `TTFT_ms` is only defined for streaming traces that emit `first_token`.
- `Final chars` uses normalized character counts and does not require
  retaining model text.
- `Provider stop reason` is copied from provider metadata when exposed by
  the adapter; otherwise it is reported as `unknown`.
- Artifacts remain under ignored local directories and are not committed.
