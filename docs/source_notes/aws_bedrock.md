# AWS Bedrock Guardrails

## Source Title

Configure streaming response behavior to filter content - Amazon Bedrock

## Source URL

https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-streaming.html

## Access Date

2026-04-29

## Source Last Updated

unknown

## Relevant Quoted or Paraphrased Claim

Short excerpts:

- "buffer and apply"
- "as soon as they become available"
- "subsequent chunks will be blocked"

Paraphrase: AWS documents synchronous and asynchronous guardrail modes for
streaming response filtering. In synchronous mode, chunks are buffered and
scanned before release. In asynchronous mode, chunks are sent immediately while
policies are applied in the background; inappropriate content may be visible
until scanning completes, and subsequent chunks are blocked after detection.

## Semantics Extracted

- response_mode: `streaming_synchronous_guardrails`; `streaming_asynchronous_guardrails`
- release_policy: `buffered_streaming`; `immediate_streaming`
- moderation_timing: `guardrails_scan_chunks_before_user_release`; `asynchronous_background_guardrail_scan`
- safety_signal_surface: `guardrail_blocking_of_subsequent_chunks`
- validation_watermark: unknown_from_official_docs
- refusal_semantics: unknown_from_official_docs
- settlement_semantics: `subsequent_chunks_blocked_after_inappropriate_content_detected`
- client_obligations: `choose_mode_based_on_latency_and_moderation_accuracy_tradeoff`
- documented_limit_or_bound: `inappropriate_content_may_appear_until_scan_completes`; `sensitive_information_masking_not_supported_in_asynchronous_mode`

## Open Questions

- Does Bedrock expose a validation watermark equivalent to Azure `check_offset`?
- What exact event shape represents a guardrail block in asynchronous streaming?
- Does the stream emit final diagnostic metadata after subsequent chunks are blocked?

## Evidence Confidence

high
