# Azure OpenAI

## Source Title

Content streaming - Azure OpenAI

## Source URL

https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/content-streaming

## Access Date

2026-04-29

## Source Last Updated

2026-02-27

## Relevant Quoted or Paraphrased Claim

Short excerpts:

- "content buffers"
- "fully vetted"
- "delayed filtering signals"
- "check_offset never decreases"

Paraphrase: Azure documents two streaming modes. Default streaming buffers
completion content, runs guardrails on buffered content, and returns vetted
chunks. Asynchronous Filter returns content immediately without buffering while
moderation runs asynchronously. In asynchronous mode, annotation and filtering
signals are delayed, `check_offset` records moderation progress, and clients are
expected to consume annotations and redact content when needed.

## Semantics Extracted

- response_mode: `streaming_default_filtering`; `streaming_asynchronous_filter`
- release_policy: `buffered_streaming`; `immediate_token_by_token_streaming`
- moderation_timing: `guardrails_run_on_buffered_content_before_return`; `asynchronous_delayed_filtering`
- safety_signal_surface: `annotation_messages_and_content_filter_finish_reason`; `content_filter_offsets_start_offset_end_offset_check_offset`; `terminal_finish_reason_content_filter`
- validation_watermark: `check_offset_character_position_fully_moderated_never_decreases`
- refusal_semantics: unknown_from_official_docs
- settlement_semantics: `stream_stops_when_content_filter_signal_is_returned`
- client_obligations: `choose_default_streaming_when_immediate_filtering_is_required`; `consume_annotations_and_implement_client_side_redaction`
- documented_limit_or_bound: `filtering_signal_within_about_1000_characters`

## Open Questions

- Are all annotation categories available across every supported model and API version?
- Can client-visible offsets drift after Unicode normalization or SDK decoding?
- Does Azure expose a final settlement event after delayed annotations complete?

## Evidence Confidence

high
