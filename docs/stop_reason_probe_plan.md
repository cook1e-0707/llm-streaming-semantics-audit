# Stop Reason Probe Plan

This probe studies terminal semantics under a larger benign output budget. It
does not use unlimited generation, unsafe prompts, or benchmark prompt imports.

## Why Not Infinite

Provider APIs require bounded generation controls, and unbounded output would
make cost, timeout, and rate-limit behavior difficult to interpret. The probe
therefore uses a high but explicit output budget and a finite benign prompt that
asks the model to finish naturally.

## Default Manifest

```text
docs/stop_reason_probe_manifest.example.toml
```

The example manifest plans six calls:

- 3 providers
- 2 response modes
- 1 benign stop-reason prompt
- 1 repetition

The output budget is intentionally much higher than the ordinary pilot but
still finite:

```text
max_output_tokens = 12048
timeout_seconds = 900
```

Some provider/model combinations may reject this value if it exceeds the
configured model limit. Treat that as configuration evidence, not as a model
behavior result, and lower the per-run budget before interpreting stop reasons.

## Dry Run

```bash
python scripts/run_benign_batch.py \
  --manifest docs/stop_reason_probe_manifest.example.toml
```

## Manual Network Opt-In

```bash
python scripts/run_benign_batch.py \
  --manifest docs/stop_reason_probe_manifest.example.toml \
  --allow-network \
  --max-total-calls 6
```

## Interpretation

The useful observation is whether the terminal boundary reports a natural
completion reason or a length-related reason. A length-related stop reason means
the output budget still constrained the run. A natural stop reason means the
prompt completed before the output budget was exhausted.

The probe remains benign-only and does not support safety claims.
