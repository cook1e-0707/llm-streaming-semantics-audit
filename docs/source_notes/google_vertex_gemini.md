# Google Gemini / Vertex AI

## Source Title

Vertex AI Gemini inference, FinishReason, and safety filters

## Source URLs

- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference
- https://docs.cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform_v1.types.Candidate.FinishReason
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/configure-safety-filters

## Access Date

2026-04-29

## Source Last Updated

- inference: 2026-04-24 UTC
- FinishReason: 2026-04-01 UTC
- safety filters: 2026-04-24 UTC

## Relevant Quoted or Paraphrased Claim

Short excerpts:

- "finishReason"
- "content is empty"
- "filters act as a barrier"

Paraphrase: Vertex AI documents streaming generation for Gemini. Its response
schema exposes finish reasons, including safety, blocklist, prohibited content,
and SPII-related stops. The Python client reference states that in streaming,
content is empty when content filters block output. The safety filter guide
describes filters as barriers that block harmful output without directly
steering model behavior.

## Semantics Extracted

- response_mode: `streaming_supported`
- release_policy: unknown_from_official_docs
- moderation_timing: `safety_and_content_filters_block_potentially_harmful_output`
- safety_signal_surface: `finish_reason_safety_blocklist_prohibited_content_spii_and_related_reasons`; `python_candidate_finish_reason_safety`
- validation_watermark: unknown_from_official_docs
- refusal_semantics: unknown_from_official_docs
- settlement_semantics: `finish_reason_explains_why_token_generation_stopped`
- client_obligations: `configure_blocking_thresholds_for_use_case`
- documented_limit_or_bound: `candidate_content_empty_if_content_filters_block_output`; `when_streaming_content_empty_if_filters_block_output`

## Open Questions

- Does Vertex/Gemini document release-before-validation timing for streaming?
- Is there a documented validation watermark for streamed safety filtering?
- Which SDKs preserve blocked-content metadata in identical shapes?

## Evidence Confidence

high
