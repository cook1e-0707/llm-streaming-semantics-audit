# Anthropic Messages Benign Pilot Summary

This report summarizes the latest redacted trace for each benign prompt
and response mode under `artifacts/real_pilot/anthropic_messages`.

## Status

- Phase: P2 real benign pilot result consolidation
- Provider: `anthropic_messages`
- Latest trace start: `2026-04-29T04:52:36.730456+00:00`
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
| `benign_summary` | `streaming` | `claude-haiku-4-5-20251001` | yes | 10 | 2 | 93 | 2081.134 | 2087.804 | 0.019 | `complete` | `end_turn` |
| `benign_summary` | `nonstreaming` | `claude-haiku-4-5-20251001` | yes | 6 | 0 | 93 | 1122.695 | n/a | 0.013 | `complete` | `end_turn` |
| `long_text_generation` | `streaming` | `claude-haiku-4-5-20251001` | yes | 16 | 8 | 711 | 1330.583 | 1332.683 | 0.021 | `length` | `max_tokens` |
| `long_text_generation` | `nonstreaming` | `claude-haiku-4-5-20251001` | yes | 6 | 0 | 709 | 2214.317 | n/a | 0.010 | `length` | `max_tokens` |
| `numbered_list_generation` | `streaming` | `claude-haiku-4-5-20251001` | yes | 15 | 7 | 507 | 806.623 | 809.193 | 0.030 | `length` | `max_tokens` |
| `numbered_list_generation` | `nonstreaming` | `claude-haiku-4-5-20251001` | yes | 6 | 0 | 518 | 1819.884 | n/a | 0.011 | `length` | `max_tokens` |
| `short_text_generation` | `streaming` | `claude-haiku-4-5-20251001` | yes | 10 | 2 | 81 | 1364.855 | 1367.794 | 0.017 | `complete` | `end_turn` |
| `short_text_generation` | `nonstreaming` | `claude-haiku-4-5-20251001` | yes | 6 | 0 | 81 | 846.725 | n/a | 0.010 | `complete` | `end_turn` |
| `structured_json_generation` | `streaming` | `claude-haiku-4-5-20251001` | yes | 12 | 4 | 256 | 909.772 | 911.756 | 0.018 | `complete` | `end_turn` |
| `structured_json_generation` | `nonstreaming` | `claude-haiku-4-5-20251001` | yes | 6 | 0 | 256 | 1124.111 | n/a | 0.011 | `complete` | `end_turn` |

## Notes

- `TTFB_ms` is measured from normalized `request_start` to `first_byte`.
- `TTFT_ms` is only defined for streaming traces that emit `first_token`.
- `Final chars` uses normalized character counts and does not require
  retaining model text.
- `Provider stop reason` is copied from provider metadata when exposed by
  the adapter; otherwise it is reported as `unknown`.
- Artifacts remain under ignored local directories and are not committed.
