# Phase 2 Real Provider Pilot Plan

P2.M2 prepares a small, benign-only raw provider pilot. It does not authorize
safety-signal experiments, benchmark imports, or framework propagation studies.

## Why Benign-Only

The first real API traces validate the harness against real provider event
surfaces. They are not designed to measure provider safety behavior. Benign
prompts keep failure analysis focused on event mapping, timing, recorder
behavior, and validator rules.

## Raw Provider Layer First

Provider behavior must be measured before SDK, framework, application, or
user-visible layers are studied. The raw provider layer provides the baseline
for later propagation analysis.

## First Provider

OpenAI Responses API is the first prepared adapter because its streaming API is
documented as typed semantic events that map naturally into normalized trace
events. This makes it suitable for harness validation.

## Second Provider Preview

Anthropic Messages streaming is a suitable later adapter because it exposes an
SSE event flow and can stream partial structured deltas. In this milestone it is
only a skeleton; it must not run network calls.

## Non-Claims

P2.M2 is not allowed to claim that a provider is safer, less safe, stricter, or
more reliable. It may only claim that benign lifecycle events can or cannot be
captured and mapped by the harness.

## Network Guard

All real API calls require explicit `--allow-network`. Scripts default to
dry-run mode and must refuse unknown prompt IDs, missing environment variables,
or unsafe output locations.

The OpenAI pilot uses the official Python SDK lazily. Install provider extras
before a real run:

```bash
python -m pip install '.[providers]'
```

Then export credentials into the shell without printing them:

```bash
set -a
source .env
set +a
```

The script does not read or print `.env` by default.
