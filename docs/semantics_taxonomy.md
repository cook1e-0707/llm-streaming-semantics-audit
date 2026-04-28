# Semantics Taxonomy

This document defines the observable runtime concepts used by the audit. Terms
are defined at the trace level so they can be compared across providers,
SDKs, frameworks, applications, and user-visible renderers.

## Concepts

### Release Policy

The rule that determines when generated content is emitted from one layer to the
next. A release policy can block until a final response exists, buffer chunks
until a validation condition is met, or immediately release chunks as they
arrive.

### Blocking Response

A response mode where the client receives the answer only after the provider or
SDK returns a terminal response object. Intermediate tokens, annotations, or
validation steps may exist but are not emitted as stream events.

### Buffered Streaming

A streaming mode where generated content is withheld or delayed until a buffer
condition is satisfied. The condition may be based on token count, time,
validation status, transport behavior, or provider policy.

### Immediate Streaming

A streaming mode where generated content is emitted to the next layer as soon as
it is available to that layer, without waiting for a later validation or
settlement event.

### Validation Boundary

The point in a trace where a layer marks content, a span, or a response as
validated, filtered, refused, or otherwise safety-relevant. The boundary can be
per-token, per-span, per-chunk, per-response, or terminal-only.

### Visibility Boundary

The point where content becomes visible to a user, persistent log, downstream
component, or tool. Visibility is layer-specific and is not equivalent to
provider release.

### Safety Signal

Any event that communicates safety-relevant information, including moderation
annotations, content filters, refusal indications, blocked spans, warning
metadata, or terminal safety reasons.

### Refusal Signal

A safety signal indicating that the model or provider declined to comply with a
request or stopped generation for refusal-related reasons.

### Validation Watermark

An observable marker identifying how far into the emitted content validation has
advanced. A watermark may be expressed in characters, tokens, bytes, event
indices, timestamps, or provider-specific offsets.

### Retroactive Invalidation

A later event that invalidates, filters, refuses, or reverses the safety status
of content that was already emitted to a downstream layer.

### Settlement Event

The event after which a trace is considered complete by a layer and no further
content, safety, refusal, filter, or repair events are expected for that trace.

### Action-Commit Boundary

The point where an agent, framework, or application commits a tool call,
database write, external action, or user-visible side effect based on generated
content.

### Provider Layer

Events visible at the provider API boundary, including raw wire events, response
objects, chunks, annotations, terminal reasons, and errors.

### SDK Layer

Events visible after a provider SDK has parsed, transformed, buffered, retried,
or normalized provider-layer events.

### Framework Layer

Events visible after an orchestration framework, agent framework, or abstraction
library has transformed SDK-layer behavior.

### Application Layer

Events produced by the application consuming SDK or framework events, including
logging, persistence, rendering decisions, and tool dispatch.

### User-Visible Layer

Events that represent content or actions actually exposed to an end user through
a UI, notification, exported artifact, or other human-facing surface.

## Observable Trace Fields

| Concept | Observable fields |
| --- | --- |
| release policy | `response_mode`, `release_policy`, `event_type`, `timestamp_ms`, `layer` |
| blocking response | `response_mode`, `final_response`, `timestamp_ms`, `terminal_reason` |
| buffered streaming | `response_mode`, `release_policy`, `chunk`, `timestamp_ms`, `validation_range` |
| immediate streaming | `response_mode`, `release_policy`, `first_token`, `chunk`, `timestamp_ms` |
| validation boundary | `safety_signal`, `validation_range`, `timestamp_ms`, `layer` |
| visibility boundary | `layer`, `event_type`, `content`, `timestamp_ms`, `metadata.visibility` |
| safety signal | `safety_signal.signal_type`, `event_type`, `terminal_reason`, `raw_payload` |
| refusal signal | `event_type`, `safety_signal.signal_type`, `terminal_reason` |
| validation watermark | `validation_range`, `sequence_index`, `char_count`, `token_count` |
| retroactive invalidation | `event_type`, `validation_range`, `metadata.invalidates_event_ids` |
| settlement event | `event_type=settled`, `timestamp_ms`, `terminal_reason`, `layer` |
| action-commit boundary | `event_type=tool_call_commit`, `tool_call_id`, `timestamp_ms`, `layer` |
| provider layer | `layer=provider`, `raw_payload`, `event_type` |
| SDK layer | `layer=sdk`, `metadata.sdk_name`, `event_type` |
| framework layer | `layer=framework`, `metadata.framework_name`, `event_type` |
| application layer | `layer=application`, `metadata.component`, `event_type` |
| user-visible layer | `layer=user_visible`, `metadata.surface`, `event_type` |
