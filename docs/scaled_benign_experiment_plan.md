# Scaled Benign Experiment Plan

This plan prepares larger benign lifecycle runs without changing the safety
boundary. It is for throughput, trace consistency, and cost-control validation,
not for safety-signal claims.

## Goal

Scale from single provider/prompt pilots to a small matrix of:

- provider
- response mode
- benign prompt category
- repetition

The runner must remain dry-run by default. Real provider calls require explicit
`--allow-network`.

## Allowed

- benign prompt IDs from `src/lssa/prompts/benign_prompts.yaml`
- OpenAI Responses, Anthropic Messages, and AWS Bedrock Converse provider layers
- streaming and non-streaming modes
- redacted JSONL traces under ignored `artifacts/`
- aggregate summaries and lifecycle comparison documents

## Forbidden

- unsafe prompts
- jailbreak datasets
- safety-signal claims
- framework integrations
- raw prompt text or full raw provider payloads in git
- network calls without explicit `--allow-network`

## Default Dry Run

```bash
python scripts/run_benign_batch.py \
  --manifest docs/benign_experiment_manifest.example.toml
```

## Manual Network Opt-In

```bash
python scripts/run_benign_batch.py \
  --manifest docs/benign_experiment_manifest.example.toml \
  --allow-network \
  --max-total-calls 12
```

Use `--force` only after manually reviewing the manifest, cost limits, and
provider quotas.

## Scale-Up Rule

Increase only one dimension at a time:

1. more repetitions
2. more benign prompt IDs
3. more models
4. more providers

Do not introduce safety prompts as part of benign scale-up.

## Stop-Reason Probe

Use `docs/stop_reason_probe_manifest.example.toml` when the goal is to observe
provider terminal semantics under a larger benign output budget. The probe uses
`max_output_tokens = 12048`, a longer timeout, and a finite benign prompt. It
is still dry-run by default and must be run with explicit `--allow-network` for
real provider calls. If a provider rejects the budget as above a model limit,
record that as a configuration constraint and rerun with a provider-compatible
bounded value.
