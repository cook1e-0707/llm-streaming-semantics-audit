# Legacy Project Notes

## Legacy Path

`/Users/guanjie/Documents/llm_api/streaming_or_not/streaming-vs-nonstreaming`

## Status

The legacy project is a prior experiment codebase for comparing streaming and
non-streaming LLM API behavior. It remains useful as a historical baseline and
possible source of concepts, but it is not the source of truth for this new
repository.

## Potentially Reusable Components

- High-level ideas for provider adapters
- Prior runner structure, after schema review
- Prior metric names, after semantic redefinition
- Prior analysis questions, after mapping to the new taxonomy

## Components That Must Not Be Copied

- `.env` files
- `keys/`
- `.venv/`
- `results/`
- `results_chimera/`
- `logs/`
- `data/raw/`
- large raw provider outputs
- raw unsafe prompt text

## Conceptual Mismatch

The legacy project frames the question as streaming versus non-streaming
behavior. The new project frames the question as runtime safety semantics across
release, validation, visibility, refusal, settlement, and action-commit
boundaries. Code should not be migrated until it can preserve those boundaries.

## Migration Policy

- Migrate concepts before code.
- Migrate schema only after reviewing compatibility.
- Migrate provider adapters only after the new trace schema is stable.
- Never migrate raw results into the repo.
- Never migrate secrets or environment files.
