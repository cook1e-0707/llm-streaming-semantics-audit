# Phase 1 Unknown-Field and Open-Questions Review

This review records what the official documentation evidence does not establish.
Unknown fields are not failures to be patched over. They are documented limits
of the current public contract baseline and should become Phase 2 observation
targets only after the benign raw API harness exists.

The review is based on `docs/provider_evidence.yaml` and the generated
`docs/provider_matrix.md`. It uses only the official documentation sources
already recorded in the provider evidence registry.

## Review Result

P1.M4 is complete when:

- every unknown provider-matrix field is explicit;
- every non-unknown field is backed by a source claim;
- source-note open questions are consolidated into testable future questions;
- no unknown field is filled by inference, memory, or non-official sources.

The current matrix satisfies those conditions. The remaining unknown fields are
valid research findings from official documentation, not missing implementation.

## Unknown Fields by Provider

| provider_family | unknown fields | review note |
| --- | --- | --- |
| OpenAI / OpenAI Guardrails | `safety_signal_surface`, `validation_watermark`, `refusal_semantics`, `settlement_semantics` | The source documents release and guardrail timing, but not concrete stream safety event shapes, watermarks, refusal terminal semantics, or settlement events. |
| Azure OpenAI | `refusal_semantics` | The source strongly documents buffering, asynchronous filtering, annotations, `check_offset`, and content-filter termination, but does not define refusal semantics for this audit axis. |
| AWS Bedrock Guardrails | `validation_watermark`, `refusal_semantics` | The source documents synchronous/asynchronous release timing and subsequent chunk blocking, but not a validation watermark or refusal-specific terminal semantics. |
| Anthropic Claude | `release_policy`, `validation_watermark` | The source documents streaming refusal control flow and context reset obligations, but not the general release policy or validation watermark. |
| Google Gemini / Vertex AI | `release_policy`, `validation_watermark`, `refusal_semantics` | The sources document streaming support, finish reasons, blocked-content behavior, and filter role, but not release-before-validation timing, validation watermark, or refusal semantics. |
| OpenAI Agents SDK | `release_policy`, `moderation_timing`, `safety_signal_surface`, `validation_watermark`, `refusal_semantics` | The source is framework-layer documentation. It supports settlement and client-consumption obligations, but not provider release, moderation, watermark, or refusal semantics. |

## Consolidated Open Questions

### Release and Visibility

- Does OpenAI Guardrails expose a concrete user-visible event when output
  guardrails trigger during streaming?
- Does Google Vertex/Gemini document any release-before-validation or buffering
  behavior beyond generic streaming examples?
- Do framework-level streaming surfaces ever reorder or delay provider-visible
  chunks before application visibility?

### Validation Watermarks

- Does AWS Bedrock expose a moderation progress marker equivalent to Azure
  `check_offset`?
- Does Anthropic expose any stream offset, span, or marker tied to classifier
  intervention?
- Do Google SDKs expose a validation boundary when content filters block output?

### Refusal and Terminal Semantics

- How should Anthropic `stop_reason: refusal` be mapped against provider
  content-filter stops from Azure or Google finish reasons?
- Do OpenAI Guardrails and AWS Bedrock expose refusal-specific semantics, or only
  filtering/blocking semantics?
- Is a terminal safety reason sufficient to define trace settlement, or can
  post-terminal annotation or cleanup events still arrive?

### Client Obligations

- Which providers require client-side redaction after delayed safety signals?
- Which providers require conversation state repair after a refusal or block?
- Which SDK/framework surfaces require continued event consumption after the
  last visible token?

## Phase 2 Implications

Phase 2 must remain benign-only. The unknown fields above should shape the raw
API harness design, but they must not be tested with unsafe prompts yet.

The benign pilot should first verify that the harness can record:

- request start and send timestamps;
- first-byte and first-token timestamps;
- chunk ordering;
- stream end and iterator end;
- final response events;
- explicit settlement events where the SDK or framework exposes them.

Only after that should Phase 3 introduce safety-signal categories for
validation-lag, exposure-window, and retroactive-invalidation measurements.
