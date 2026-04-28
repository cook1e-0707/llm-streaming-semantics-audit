# Research Charter

## Problem Statement

Streaming LLM APIs can release partial output before all validation, filtering,
or refusal signals have been observed by a client. Non-streaming APIs can also
hide intermediate validation and settlement behavior. This project studies those
runtime semantics as black-box, observable systems behavior.

The central problem is not whether one response mode is faster. The central
problem is how release, validation, visibility, refusal, settlement, and action
commitment interact when output is progressively exposed to users or downstream
tools.

## Motivation

Applications increasingly connect streamed LLM output to user interfaces,
databases, tool calls, agents, and workflow systems. A token that is visible for
only a short time can still be copied, logged, rendered, persisted, or used to
trigger an action. Runtime safety semantics therefore matter independently from
final response quality.

Provider documentation and SDK abstractions do not always expose the same
semantic layer. A provider-level safety signal can be delayed, transformed, or
lost before it reaches an application. A framework can also commit an action
before a later safety or refusal signal is visible to the caller.

## Research Questions

RQ1. What release policies do commercial black-box LLM APIs expose in streaming
and non-streaming modes?

RQ2. Where are validation boundaries, visibility boundaries, settlement events,
and action-commit boundaries observable in provider, SDK, framework,
application, and user-visible traces?

RQ3. How long can content remain visible before a safety signal, refusal signal,
or retroactive invalidation is observable by the client?

RQ4. Which terminal reasons and safety signals remain consistent across
provider, SDK, framework, and application layers?

RQ5. What repair burden is imposed on clients when a provider or framework emits
delayed validation, refusal, or filtering information?

## What This Project Is Not

This project is not a model-quality benchmark, a latency-only benchmark, a
provider ranking, a jailbreak benchmark, or a moderation-model training effort.
It does not aim to publish raw unsafe prompts or raw provider outputs.

## Threat Model

The project assumes a client application that consumes provider or framework
events through documented APIs. The client may render partial output, persist
logs, pass content to tools, or commit agent actions while a stream is still in
progress. The audit observes externally visible behavior and does not rely on
provider internals.

In scope threats include delayed safety signals, release-before-validation,
retroactive invalidation, inconsistent terminal reasons, and action commits that
occur before stream settlement.

Out of scope threats include provider-side training data extraction, hidden
internal classifiers, network-layer compromise, and attacks requiring private
provider infrastructure access.

## Ethical and Data-Handling Policy

The repository must not contain API keys, private credentials, `.env` files,
local key files, large raw result dumps, or raw unsafe prompt text. Documentation
may describe risk categories at a high level. Fixtures should be synthetic,
benign, redacted, or aggregate-only unless a later review explicitly approves a
different policy.

Provider behavior must not be fabricated. If a behavior is not backed by an
official source, source note, or collected trace, it must be recorded as
`TODO(source needed)` or `unknown`.

## Phase 0 Deliverables

- Research charter
- Semantics taxonomy
- Provider documentation matrix template
- Metrics definitions
- Trace event schema
- Basic metric functions
- README status generation
- Tests for schema, metrics, and README status behavior

## Phase 1 Preview

Phase 1 will audit official provider documentation and map documented behavior
onto the taxonomy. It will not run provider API calls or infer behavior from
memory. Unsupported claims remain explicit unknowns until evidence is recorded.
