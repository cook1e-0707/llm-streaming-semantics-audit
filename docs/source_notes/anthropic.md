# Anthropic Claude

## Source Title

Streaming refusals - Claude API Docs

## Source URL

https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/handle-streaming-refusals

## Access Date

2026-04-29

## Source Last Updated

unknown

## Relevant Quoted or Paraphrased Claim

Short excerpts:

- "stop_reason refusal"
- "No additional refusal message"
- "reset the conversation context"

Paraphrase: Anthropic documents streaming classifier intervention as
`stop_reason` refusal. The refusal can occur during streaming when content
violates policy, no additional refusal message is included, and callers must
reset or update the refused turn before continuing. Usage metrics and billing
can still apply up to the refusal.

## Semantics Extracted

- response_mode: `streaming`
- release_policy: unknown_from_official_docs
- moderation_timing: `classifier_intervention_during_streaming`
- safety_signal_surface: `stop_reason_refusal`
- validation_watermark: unknown_from_official_docs
- refusal_semantics: `streaming_classifier_refusal_control_event`
- settlement_semantics: `no_additional_refusal_message_usage_metrics_still_provided`
- client_obligations: `reset_or_update_conversation_context_after_refusal`
- documented_limit_or_bound: `billed_for_output_tokens_until_refusal`

## Open Questions

- Does the API expose the exact generated span that triggered the refusal?
- Is there an explicit settlement event after refusal besides stream termination?
- Are refusal semantics identical across Claude model families?

## Evidence Confidence

high
