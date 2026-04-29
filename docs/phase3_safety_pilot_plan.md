# Phase 3 Safety Pilot Plan

This plan prepares real safety-signal experiments from an external prompt
source. It is staged so the project can scale without committing raw unsafe
prompts or full provider outputs.

## Stage 1: Inventory

Inspect the external prompt source without printing raw prompt text:

```bash
python scripts/inspect_external_safety_prompts.py
```

## Stage 2: Dry Run

Generate a redacted plan for one provider and one prompt:

```bash
python scripts/run_safety_signal_pilot.py \
  --provider openai_responses \
  --mode streaming \
  --limit 1 \
  --max-calls 1
```

This must print `network=disabled`.

## Stage 3: Small Reviewed Pilot

Only after reviewing the source and stop conditions:

```bash
python scripts/run_safety_signal_pilot.py \
  --provider openai_responses \
  --mode streaming \
  --limit 1 \
  --max-calls 1 \
  --allow-network \
  --allow-safety-prompts \
  --reviewed-source
```

## Stage 4: Controlled Scale-Up

Increase only one dimension at a time:

1. more prompts
2. non-streaming pair for the same provider
3. second provider
4. more categories
5. more repetitions

Do not jump from one prompt to the full dataset.

## Stop Conditions

Stop the run if any of these occur:

- trace validation fails
- provider rejects the prompt source or model configuration
- content fields are not redacted in artifacts
- rate limits or timeout errors become frequent
- costs exceed the reviewed budget
- safety output appears in tracked files

## Readiness Check

```bash
python scripts/check_p3_safety_pilot_ready.py
```

The check confirms external source access, redacted dry-run planning, and
double opt-in guards. It does not authorize real calls by default.
