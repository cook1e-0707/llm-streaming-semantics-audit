# Provider Documentation Matrix

This matrix is generated from `docs/provider_evidence.yaml`. Do not edit
the table by hand; update the evidence registry and run
`python scripts/generate_provider_matrix.py`.

Unsupported fields are rendered as `unknown_from_official_docs` until
an official documentation claim supports a more specific value.

| provider_family | api_surface | response_mode | release_policy | moderation_timing | safety_signal_surface | validation_watermark | refusal_semantics | settlement_semantics | client_obligations | documented_limit_or_bound | source_id | evidence_status | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI / OpenAI Guardrails | OpenAI Guardrails Python | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | openai_guardrails_streaming_output | TODO(source needed) | unknown |
| Azure OpenAI | Azure OpenAI content streaming | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | azure_openai_content_streaming | TODO(source needed) | unknown |
| AWS Bedrock Guardrails | Amazon Bedrock Guardrails streaming | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | aws_bedrock_guardrails_streaming | TODO(source needed) | unknown |
| Anthropic Claude | Claude streaming refusals | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | anthropic_streaming_refusals | TODO(source needed) | unknown |
| Google Gemini / Vertex AI | Vertex AI Gemini safety and inference | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | google_vertex_gemini_safety | TODO(source needed) | unknown |
| OpenAI Agents SDK | OpenAI Agents Python streaming results | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | openai_agents_sdk_results | TODO(source needed) | unknown |
