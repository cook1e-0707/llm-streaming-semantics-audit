# P3 Overnight Batch Runner

`scripts/run_p3_overnight_batch.py` coordinates guarded Phase 3 safety-signal
runs across provider, response-mode, and optional judge-adjudication tasks.

The runner is conservative by default:

- no provider network calls unless `--allow-network` is present
- no judge network calls unless `--allow-judge-network` is present
- no raw safety prompt text is loaded unless `--allow-safety-prompts` and
  `--reviewed-source` are also present
- batches larger than three prompts require `--force`
- all plans, traces, logs, judge outputs, and summaries are written under
  ignored `artifacts/`

## Dry Run

```bash
python scripts/run_p3_overnight_batch.py \
  --providers all \
  --modes streaming,nonstreaming \
  --limit-per-provider-mode 10 \
  --judge-limit 10 \
  --judge-profile all
```

## Real Overnight Run

Load local environment variables first, then run with explicit opt-in:

```bash
set -a
source .env
set +a

python scripts/run_p3_overnight_batch.py \
  --providers all \
  --modes streaming,nonstreaming \
  --limit-per-provider-mode 30 \
  --judge-limit 30 \
  --judge-profile all \
  --max-output-tokens 512 \
  --timeout-seconds 90 \
  --allow-network \
  --allow-judge-network \
  --allow-safety-prompts \
  --reviewed-source \
  --force
```

This schedule creates up to 180 provider calls and 60 judge calls. Increase only
after verifying cost, rate limits, and artifact structure.

## Judge Provider Outputs

Prompt-level judge adjudication labels the source prompts. To judge every model
output, use response-level judging:

```bash
python scripts/run_p3_overnight_batch.py \
  --providers all \
  --modes streaming,nonstreaming \
  --limit-per-provider-mode 50 \
  --judge-limit 0 \
  --judge-responses \
  --judge-profile all \
  --max-output-tokens 512 \
  --timeout-seconds 90 \
  --allow-network \
  --allow-judge-network \
  --allow-safety-prompts \
  --reviewed-source \
  --force
```

This creates up to 300 provider calls and 600 response-level judge result
records. Provider output text is passed to the judge in memory and is not
written to disk; artifacts store labels, hashes, lengths, and trace metadata.

## Outputs

Each run creates:

```text
artifacts/p3_overnight/<run_id>/
  manifest.json
  logs/
  plans/
  safety_signal/
  judge_adjudication/
  p3_overnight_summary.json
```

The summary aggregates terminal reasons, provider stop reasons, event type
counts, and judge labels. It does not store raw prompt text.

After a run has completed, compute post-hoc P3 metrics, including per-chunk
streaming latency aggregates:

```bash
python scripts/summarize_p3_run.py \
  --run-root artifacts/p3_overnight/<run_id>
```

This writes `p3_run_metrics.json` under the run directory.

## Interpretation

P3 overnight runs are safety-signal timing measurements. Judge labels are
secondary annotations and must not be treated as provider runtime semantics.
