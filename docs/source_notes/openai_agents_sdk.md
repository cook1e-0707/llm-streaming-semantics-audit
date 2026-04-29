# OpenAI Agents SDK

## Source Title

Results - OpenAI Agents SDK

## Source URL

https://openai.github.io/openai-agents-python/results/

## Access Date

2026-04-29

## Source Last Updated

unknown

## Relevant Quoted or Paraphrased Claim

Short excerpts:

- "streaming-specific controls"
- "final_output stays None"
- "not complete until that iterator ends"
- "continue consuming stream_events"

Paraphrase: OpenAI Agents SDK documents `RunResultStreaming` as adding
stream-specific controls. In streaming mode, `final_output` stays unavailable
until stream processing finishes. A streaming run is not complete until the
async iterator ends, and summary properties plus session persistence side
effects may settle after the last visible token. After cancellation, clients
should keep consuming events so cleanup can finish.

## Semantics Extracted

- response_mode: `framework_streaming_result`
- release_policy: unknown_from_official_docs
- moderation_timing: unknown_from_official_docs
- safety_signal_surface: unknown_from_official_docs
- validation_watermark: unknown_from_official_docs
- refusal_semantics: unknown_from_official_docs
- settlement_semantics: `streaming_result_has_is_complete_and_stream_events_controls`; `final_output_none_until_stream_finished_processing`; `stream_not_complete_until_async_iterator_ends`
- client_obligations: `continue_consuming_stream_events_until_iterator_finishes`; `after_cancel_continue_consuming_stream_events_for_cleanup`
- documented_limit_or_bound: `summary_properties_and_session_side_effects_may_settle_after_last_visible_token`

## Open Questions

- How should SDK settlement be compared with provider wire-level settlement?
- Which event should define application-level commit readiness?
- Are guardrail result arrays updated after the last user-visible token?

## Evidence Confidence

high
