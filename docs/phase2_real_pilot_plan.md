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

## Second Provider

Anthropic Messages streaming is the second prepared adapter because it exposes
an SSE event flow with `message_start`, `content_block_delta`, `message_delta`,
and `message_stop` events. It must follow the same benign-only, dry-run-by-
default, `--allow-network` opt-in policy as OpenAI.

## Non-Claims

P2.M2 is not allowed to claim that a provider is safer, less safe, stricter, or
more reliable. It may only claim that benign lifecycle events can or cannot be
captured and mapped by the harness.

## Network Guard

All real API calls require explicit `--allow-network`. Scripts default to
dry-run mode and must refuse unknown prompt IDs, missing environment variables,
or unsafe output locations.

The OpenAI and Anthropic pilots use official Python SDKs lazily. Install
provider extras before a real run:

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

Dry-run examples:

```bash
python scripts/run_real_benign_pilot.py --provider openai_responses --dry-run
python scripts/run_real_benign_pilot.py --provider anthropic_messages --dry-run
```

## Bedrock Configuration Only

`AWS_BEARER_TOKEN_BEDROCK` may be configured locally for future Bedrock Runtime
work. P2.M3 does not add a Bedrock adapter or run Bedrock calls. The current
repository support is limited to SDK dependency and redacted configuration
helpers.
