# Metrics

Each metric must identify the required events, required fields, applicable layer,
interpretation, and known failure modes. Metrics marked `implemented` have a
pure Python implementation in `src/lssa/schema/metrics.py`; metrics marked
`stub` require later unsafe-span labels or provider-specific trace evidence.

## TTFB_ms

- Status: implemented
- Definition: elapsed milliseconds from `request_start` to `first_byte`.
- Required event fields: `event_type`, `timestamp_ms`, `trace_id`.
- Applicable layer: provider, SDK.
- Interpretation: transport-visible response start latency.
- Failure modes: missing `request_start`, missing `first_byte`, clock mismatch, retries collapsed into one trace.

## TTFT_ms

- Status: implemented
- Definition: elapsed milliseconds from `request_start` to `first_token`.
- Required event fields: `event_type`, `timestamp_ms`, `trace_id`.
- Applicable layer: provider, SDK, framework, application, user-visible.
- Interpretation: first generated token visibility latency at the selected layer.
- Failure modes: providers without token events, SDK chunk aggregation, framework buffering, UI debounce.

## TTFSS_ms

- Status: implemented
- Definition: elapsed milliseconds from `request_start` to the first safety-relevant signal.
- Required event fields: `event_type`, `timestamp_ms`, `trace_id`, `safety_signal`.
- Applicable layer: provider, SDK, framework, application.
- Interpretation: how quickly a client can observe safety-relevant information after request start.
- Failure modes: safety metadata emitted only at terminal response, SDK normalization loss, source-specific signal names.

## validation_lag_chars

- Status: stub
- Definition: emitted characters beyond the latest validation watermark at the time a safety signal is observed.
- Required event fields: `event_type`, `timestamp_ms`, `char_count`, `validation_range`.
- Applicable layer: provider, SDK, framework, application, user-visible.
- Interpretation: amount of character-level release-before-validation.
- Failure modes: missing character offsets, chunk rewrites, redaction changing offsets, no unsafe-span labels.

## validation_lag_tokens

- Status: stub
- Definition: emitted tokens beyond the latest validation watermark at the time a safety signal is observed.
- Required event fields: `event_type`, `timestamp_ms`, `token_count`, `validation_range`.
- Applicable layer: provider, SDK, framework, application, user-visible.
- Interpretation: amount of token-level release-before-validation.
- Failure modes: tokenizer mismatch, SDK aggregation, missing provider token offsets, no unsafe-span labels.

## exposure_window_chars

- Status: stub
- Definition: number of characters that were visible before a later safety signal or invalidation covered them.
- Required event fields: `event_type`, `timestamp_ms`, `content`, `validation_range`, `safety_signal`.
- Applicable layer: application, user-visible.
- Interpretation: character-level size of content exposure before repair or invalidation.
- Failure modes: no visibility trace, no invalidated span labels, UI redaction not represented in trace.

## exposure_window_tokens

- Status: stub
- Definition: number of tokens that were visible before a later safety signal or invalidation covered them.
- Required event fields: `event_type`, `timestamp_ms`, `token_count`, `validation_range`, `safety_signal`.
- Applicable layer: application, user-visible.
- Interpretation: token-level size of content exposure before repair or invalidation.
- Failure modes: tokenizer mismatch, no unsafe-span labels, token offsets unavailable after redaction.

## exposure_window_ms

- Status: stub
- Definition: elapsed milliseconds between first visibility of later-invalidated content and the safety signal or repair event.
- Required event fields: `event_type`, `timestamp_ms`, `validation_range`, `safety_signal`.
- Applicable layer: application, user-visible.
- Interpretation: temporal duration of potentially unsafe visibility.
- Failure modes: missing visibility boundary, missing invalidation event, asynchronous rendering not traced.

## retroactive_invalidation

- Status: stub
- Definition: boolean indicator that a later event invalidated, filtered, or refused content already emitted to a downstream layer.
- Required event fields: `event_type`, `timestamp_ms`, `validation_range`, `metadata.invalidates_event_ids`.
- Applicable layer: provider, SDK, framework, application, user-visible.
- Interpretation: whether released content had to be reversed or repaired after exposure.
- Failure modes: provider does not identify invalidated spans, client drops metadata, repair performed outside trace.

## terminal_reason_consistency

- Status: stub
- Definition: whether terminal reasons agree across provider, SDK, framework, application, and user-visible layers for one trace.
- Required event fields: `event_type`, `timestamp_ms`, `terminal_reason`, `layer`.
- Applicable layer: provider, SDK, framework, application, user-visible.
- Interpretation: consistency of completion, refusal, filter, cancel, and error semantics across layers.
- Failure modes: SDK maps multiple reasons into one value, framework overwrites terminal reason, missing terminal event.

## settlement_lag_ms

- Status: implemented
- Definition: elapsed milliseconds between the last terminal output event and `settled`.
- Required event fields: `event_type`, `timestamp_ms`, `trace_id`.
- Applicable layer: provider, SDK, framework, application.
- Interpretation: post-output time before a layer considers the trace complete.
- Failure modes: no explicit settlement event, multiple terminal events, event ordering errors.

## client_repair_burden

- Status: stub
- Definition: count or structured score of client-side actions needed after delayed safety, refusal, filtering, or invalidation.
- Required event fields: `event_type`, `timestamp_ms`, `metadata.repair_action`, `validation_range`.
- Applicable layer: application, user-visible.
- Interpretation: operational burden imposed on clients by delayed or retroactive semantics.
- Failure modes: repair actions not instrumented, UI repair differs from persisted logs, ambiguous repair policy.
