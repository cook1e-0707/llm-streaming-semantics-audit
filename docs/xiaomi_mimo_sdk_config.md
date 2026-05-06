# Xiaomi MiMo SDK Configuration

This document records local SDK configuration for Xiaomi MiMo pilots. It does
not authorize provider calls.

## Credential Variable

Use one of these local environment variables:

```text
XIAOMI_MIMO_API_KEY
MIMO_API_KEY
```

`XIAOMI_MIMO_API_KEY` is preferred for this repository. `MIMO_API_KEY` is also
accepted for compatibility with other MiMo tooling. Keep the value only in local
shell state or `.env`. Do not commit it, print it, or copy it into trace
metadata.

## Endpoints

The default Singapore token-plan endpoints are:

```text
XIAOMI_MIMO_OPENAI_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
XIAOMI_MIMO_ANTHROPIC_BASE_URL=https://token-plan-sgp.xiaomimimo.com/anthropic
```

Override these variables locally if testing a different MiMo region or plan.

## Model

The default model is:

```text
XIAOMI_MIMO_MODEL=mimo-v2-omni
```

You can override it per run with `--model`.

## Python SDK

Provider extras install the SDKs used by the compatible endpoints:

```bash
python -m pip install '.[providers]'
```

The provider adapters are:

```text
src/lssa/adapters/xiaomi_mimo.py
```

The OpenAI-compatible surface uses the OpenAI Python SDK Chat Completions API with
`XIAOMI_MIMO_OPENAI_BASE_URL`. The Anthropic-compatible surface uses the
Anthropic Python SDK with `XIAOMI_MIMO_ANTHROPIC_BASE_URL`.

## Provider Names

Use these CLI provider names:

```text
xiaomi_mimo_openai
xiaomi_mimo_anthropic
```

Real calls still require explicit `--allow-network`. Safety-prompt calls also
require the existing safety prompt opt-ins.
