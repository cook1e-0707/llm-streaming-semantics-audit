# Trace Contract

The trace contract defines how provider, SDK, framework, application, and
user-visible events are represented as normalized `StreamEvent` objects.

## Trace Lifecycle

The minimum benign lifecycle is:

```text
request_start
request_sent
first_byte
first_token
chunk*
stream_end
final_response?
iterator_end
settled
```

Non-streaming traces may omit `first_token` and `chunk`, but they still need a
request start, request send, final response, iterator end, and settlement.

Error traces terminate with `error` and `settled`. Cancellation traces must
include `cancel`, then terminal cleanup through `iterator_end` and `settled`.

## Terminal Events

- `stream_end`: provider or SDK reports no more streamed content chunks.
- `final_response`: a complete response object is available.
- `iterator_end`: the client-facing iterator or event stream has ended.
- `settled`: the layer considers the trace complete and expects no more
  content, safety, repair, cleanup, or bookkeeping events.

These events must not be collapsed. A framework or SDK may still settle state
after the last visible content token.

## Layer Separation

- Provider wire-visible events preserve provider event names in redacted
  metadata.
- SDK-visible events represent SDK parsing, buffering, retries, or normalized
  callback behavior.
- Framework events represent orchestration abstractions.
- Application events represent logging, persistence, rendering, and tool
  dispatch decisions.
- User-visible events represent content or actions exposed to humans.

P2.M1 uses provider-layer mock events only. Later phases may add SDK,
framework, application, and user-visible traces, but they must not be collapsed
into provider ground truth.

## Raw Event Mapping

Provider-specific raw event objects must not become the primary return type.
Adapters must emit normalized `StreamEvent` objects. Raw details may appear only
as redacted metadata:

```text
metadata.raw_event_type
metadata.payload_summary
metadata.payload_redacted
metadata.monotonic_time_ns
metadata.wall_time_iso
```

The default policy is to store summaries and redacted payloads, not full raw
provider output.

## Required Ordering Rules

- `request_start` appears before `request_sent`.
- `request_sent` appears before `first_byte`, when `first_byte` exists.
- `first_byte` appears before `first_token`, when `first_token` exists.
- Text `chunk` events appear after `first_token`.
- `stream_end` appears after `request_sent`.
- `iterator_end` appears after `stream_end`, when both exist.
- `settled` appears after `iterator_end`, when both exist.
- `error` is terminal unless `metadata.recoverable` is true.
- `cancel` is followed by `iterator_end` and `settled`.
- Sequence indexes are contiguous.
- Monotonic timestamps do not decrease.
