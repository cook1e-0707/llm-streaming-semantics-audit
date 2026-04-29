# External Safety Prompt Source

Phase 3 uses an external safety prompt source. Raw unsafe prompt text must not
be copied into this repository.

## Configured Source

```text
/Users/guanjie/Documents/llm_api/streaming_or_not/streaming-vs-nonstreaming/data/safety
```

Set the path through:

```bash
export LSSA_SAFETY_PROMPT_ROOT=/Users/guanjie/Documents/llm_api/streaming_or_not/streaming-vs-nonstreaming/data/safety
```

`.env.example` includes this variable, but `.env` itself remains untracked.

## Current Inventory

The source is a JSONL-based safety prompt collection with shard directories.
The loader treats it as an external controlled store and writes only redacted
metadata into this repo.

Useful commands:

```bash
python scripts/inspect_external_safety_prompts.py
python scripts/inspect_external_safety_prompts.py --json
```

The inventory command prints counts and redacted metadata only. It must not
print raw prompt text.

## Loader Rules

- load raw prompt text only for an explicitly approved network run
- do not write raw prompt text into tracked files
- write redacted plans under ignored `artifacts/`
- write redacted traces and summaries only
- require `--allow-network`, `--allow-safety-prompts`, and `--reviewed-source`
  for any real safety run

## Boundary

This document configures a prompt source. It does not authorize a large-scale
real safety experiment. Large runs must be preceded by small pilot validation,
cost review, stop conditions, and redaction checks.
