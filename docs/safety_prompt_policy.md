# Safety Prompt Policy

This policy governs future Phase 3 safety-signal pilots. It exists before any
real safety prompts are added or run.

## Non-Negotiable Rule

Do not commit raw unsafe prompt text, jailbreak text, private data, credentials,
or full provider outputs to this repository.

## Prompt Storage

Real safety prompts, if approved later, must live outside git in a controlled
local or institutional storage location. The repository may contain only:

- prompt IDs
- redacted category labels
- risk level labels
- source status
- review status
- allowed provider/mode scope
- retention policy

## Redacted Registry Shape

A future safety prompt registry may use this shape:

```yaml
prompts:
  - prompt_id: safety_category_example_001
    category: redacted_category_label
    raw_text_location: external_controlled_store
    raw_text_committed: false
    review_status: pending
    allowed_phase: P3.M2
    allowed_modes:
      - streaming
      - nonstreaming
    notes: redacted
```

The registry must not include the raw prompt body.

## Output Retention

For Phase 3, trace artifacts must remain redacted by default:

- no full model output text
- no raw unsafe prompt text
- no raw provider payloads unless separately approved and redacted
- aggregate timing metrics preferred
- local ignored artifacts only

## Review Requirements

Before P3.M2 can run, a reviewer must confirm:

- prompt categories are necessary for the research question
- prompt text is stored outside git
- prompts do not include private user data or secrets
- provider terms and institutional requirements are respected
- stop conditions are documented
- commands still require explicit `--allow-network`

## Boundary

This document authorizes policy preparation only. It does not authorize real
safety-signal API calls.
