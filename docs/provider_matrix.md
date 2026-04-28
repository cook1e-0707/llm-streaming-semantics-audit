# Provider Documentation Matrix

This matrix is a Phase 0 template for documentation audit. It must not be read
as a claim about provider behavior. Unsupported fields remain explicit
`TODO(source needed)` or `unknown` values until a source note or trace supports
them.

Allowed `evidence_status` values:

- `TODO(source needed)`: no source has been recorded.
- `unknown`: source note exists but does not support the field yet.
- `partial`: at least one field is supported, but the row remains incomplete.
- `supported`: every non-placeholder semantics field is supported by the
  evidence file.

| provider_family | api_surface | response_mode | release_policy | moderation_timing | safety_signal_surface | validation_watermark | refusal_semantics | settlement_semantics | client_obligations | evidence_file | evidence_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI / OpenAI Guardrails | unknown | unknown | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | docs/source_notes/openai_guardrails.md | TODO(source needed) |
| Azure OpenAI | unknown | unknown | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | docs/source_notes/azure_openai.md | TODO(source needed) |
| AWS Bedrock Guardrails | unknown | unknown | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | docs/source_notes/aws_bedrock.md | TODO(source needed) |
| Anthropic Claude | unknown | unknown | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | docs/source_notes/anthropic.md | TODO(source needed) |
| Google Gemini / Vertex AI | unknown | unknown | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | docs/source_notes/google_vertex_gemini.md | TODO(source needed) |
