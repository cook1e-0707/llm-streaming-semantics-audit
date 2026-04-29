# Optional Judge Adjudication Plan

The judge layer is optional and separate from provider ground truth. It may be
used later to label prompt or output semantics, but it must not replace provider
events such as `provider_stop_reason`, `terminal_reason`, `refusal`, or
`content_filter`.

## NVIDIA Guard Models

NVIDIA documents content-safety models that can act as moderators for prompts
and responses. The hosted API catalog includes `nvidia/nemotron-3-content-safety`
and related guard models. NVIDIA NeMo Platform documentation also lists
`nvidia/llama-3.1-nemotron-safety-guard-8b-v3` for content safety and notes that
content-safety NIMs expose OpenAI-compatible chat-completions endpoints.

Default local configuration:

```bash
LSSA_JUDGE_PROVIDER=nvidia_nim
LSSA_JUDGE_API_KEY_ENV=NVIDIA_API_KEY_A
LSSA_JUDGE_BASE_URL=https://integrate.api.nvidia.com/v1
LSSA_JUDGE_MODEL=nvidia/llama-3.1-nemoguard-8b-content-safety
```

The model name is configurable because NVIDIA exposes multiple guard-family
models and available model IDs may differ across hosted and self-hosted NIM
environments.

## Credential Policy

Do not paste NVIDIA API keys into chat, docs, scripts, tests, or tracked files.
If a key has been exposed, rotate it before use. The runner stores only the env
var name, not the key value.

## Dry Run

```bash
python scripts/run_judge_adjudication.py --limit 1 --max-calls 1
python scripts/check_judge_ready.py
```

Dry-run mode writes a redacted plan under ignored `artifacts/` and does not load
raw prompt text.

## Network Opt-In

Judge calls require all three flags:

```bash
python scripts/run_judge_adjudication.py \
  --limit 1 \
  --max-calls 1 \
  --allow-judge-network \
  --allow-safety-prompts \
  --reviewed-source
```

Outputs are redacted by default. The runner stores normalized labels, raw judge
response length, and a hash of the judge response, not raw prompt text.

## Interpretation

Judge labels are secondary annotations. They can support later analysis of
ambiguous outputs, but they are not evidence of provider runtime semantics.
