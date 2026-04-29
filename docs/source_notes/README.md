# Provider Source Notes

This directory stores manual documentation evidence for provider streaming
semantics. Each source note should record only claims supported by a source
consulted during the documentation audit.

The machine-readable source of truth is `docs/provider_evidence.yaml`. Markdown
notes in this directory are human-readable companions for reviewers. If a claim
appears in a source note but not in `docs/provider_evidence.yaml`, it must not
be used in `docs/provider_matrix.md`.

Rules:

- Do not invent citations.
- Do not record provider behavior from memory.
- Do not include unsafe prompt examples.
- Keep quoted text short and attribution-ready.
- Use `unknown` or `TODO(source needed)` when evidence is missing.
- Use only official provider documentation for Phase 1 matrix claims.
- Keep non-official sources out of the initial provider matrix.

Each evidence entry should use this structure in `docs/provider_evidence.yaml`:

```yaml
sources:
  - source_id: stable_unique_id
    provider_family: Provider family name
    api_surface: API surface name
    source_title: Official documentation title
    source_url: https://example.com/official-docs
    access_date: "YYYY-MM-DD"
    source_last_updated: unknown
    source_type: official_docs
    evidence_status: partial
    claims:
      - claim_id: stable_claim_id
        claim_scope:
          - release_policy
        short_excerpt: brief source excerpt
        paraphrase: concise claim paraphrase
        extracted_semantics:
          release_policy: immediate_streaming
        confidence: high
        open_questions: []
```

Allowed `claim_scope` fields:

- `response_mode`
- `release_policy`
- `moderation_timing`
- `safety_signal_surface`
- `validation_watermark`
- `refusal_semantics`
- `settlement_semantics`
- `client_obligations`
- `documented_limit_or_bound`

Allowed `evidence_status` values:

- `complete`
- `partial`
- `TODO(source needed)`
- `unknown`

Allowed `confidence` values:

- `high`
- `medium`
- `low`
- `unknown`

Evidence confidence values:

- high: direct official documentation supports the extracted semantics.
- medium: official documentation is relevant but incomplete or indirect.
- low: source is non-official or requires substantial interpretation.
- unknown: no usable source has been recorded yet.
