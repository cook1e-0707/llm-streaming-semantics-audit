# OpenAI / OpenAI Guardrails

## Source Title

Streaming vs Blocking - OpenAI Guardrails Python

## Source URL

https://openai.github.io/openai-guardrails-python/streaming_output/

## Access Date

2026-04-29

## Source Last Updated

unknown

## Relevant Quoted or Paraphrased Claim

Short excerpts:

- "guardrails complete before showing output"
- "output streams to user immediately"
- "guardrails run in parallel"

Paraphrase: OpenAI Guardrails documents non-streaming as the default safer mode
where output is shown after guardrail completion. Streaming is documented as
faster but less safe because output is released immediately while output
guardrails run concurrently, so violative content may be briefly visible before
guardrails trigger.

## Semantics Extracted

- response_mode: `non_streaming`; `streaming`
- release_policy: `blocking_pre_release_validation`; `immediate_streaming`
- moderation_timing: `output_guardrails_complete_before_visibility`; `output_guardrails_parallel_with_streaming`
- safety_signal_surface: unknown_from_official_docs
- validation_watermark: unknown_from_official_docs
- refusal_semantics: unknown_from_official_docs
- settlement_semantics: unknown_from_official_docs
- client_obligations: `use_for_high_assurance_or_compliance_critical_scenarios`; `use_for_low_risk_latency_sensitive_applications`
- documented_limit_or_bound: `violative_content_may_briefly_appear_before_guardrails_trigger`

## Open Questions

- Does this API surface expose a validation watermark for streamed output?
- Which concrete runtime event represents an output guardrail trigger?
- Are terminal safety events normalized by the Guardrails runtime?

## Evidence Confidence

high
