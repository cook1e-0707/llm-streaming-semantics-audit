# P3.M4 Judge Adjudication Plan

The judge layer is optional and separate from provider ground truth. It may be
used to label prompt or output semantics after safety traces exist, but it must
not replace provider events such as `provider_stop_reason`, `terminal_reason`,
`refusal`, `content_filter`, or validation annotations.

## NVIDIA Guard Profiles

P3.M4 uses two NVIDIA NIM guard-model profiles through the OpenAI-compatible
chat-completions surface. NVIDIA documents
`nvidia/llama-3.1-nemotron-safety-guard-8b-v3` as a content-safety model, and
documents `meta/llama-guard-4-12b` as a safety classifier for prompts and
responses.

Default local configuration:

```bash
LSSA_JUDGE_PROVIDER=nvidia_nim
LSSA_JUDGE_BASE_URL=https://integrate.api.nvidia.com/v1

LSSA_JUDGE_A_API_KEY_ENV=NVIDIA_API_KEY_A
LSSA_JUDGE_A_MODEL=nvidia/llama-3.1-nemotron-safety-guard-8b-v3

LSSA_JUDGE_B_API_KEY_ENV=NVIDIA_API_KEY_B
LSSA_JUDGE_B_MODEL=meta/llama-guard-4-12b
```

Profile A omits `max_tokens` by default because the NVIDIA NIM reference for
`nvidia/llama-3.1-nemotron-safety-guard-8b-v3` does not list that body
parameter. Profile B sends `max_tokens=30`, matching the narrow output range
documented for `meta/llama-guard-4-12b`. Profile B also sends a single `user`
message because the hosted Llama Guard 4 endpoint documents only `user` and
`assistant` message roles.

## Official References

- `nvidia/llama-3.1-nemotron-safety-guard-8b-v3`:
  `https://docs.api.nvidia.com/nim/reference/nvidia-llama-3_1-nemotron-safety-guard-8b-v3`
- Nemotron safety guard inference endpoint:
  `https://docs.api.nvidia.com/nim/reference/nvidia-llama-3_1-nemotron-safety-guard-8b-v3-infer`
- `meta/llama-guard-4-12b`:
  `https://docs.api.nvidia.com/nim/reference/meta-llama-guard-4-12b`
- Llama Guard 4 inference endpoint:
  `https://docs.api.nvidia.com/nim/reference/meta-llama-guard-4-12b-infer`

## Credential Policy

Do not paste NVIDIA API keys into chat, docs, scripts, tests, or tracked files.
If a key has been exposed outside the local `.env`, rotate it before use. The
runner stores only environment variable names, never key values.

## Dry Run

Dry run is the default. It writes a redacted plan under ignored `artifacts/` and
does not load raw prompt text.

```bash
python scripts/run_judge_adjudication.py --judge-profile all --limit 1 --max-calls 2
python scripts/check_judge_ready.py
```

Run one profile at a time when isolating model behavior:

```bash
python scripts/run_judge_adjudication.py --judge-profile a --limit 1 --max-calls 1
python scripts/run_judge_adjudication.py --judge-profile b --limit 1 --max-calls 1
```

## Network Opt-In

Judge calls require all three flags:

```bash
python scripts/run_judge_adjudication.py \
  --judge-profile all \
  --limit 1 \
  --max-calls 2 \
  --allow-judge-network \
  --allow-safety-prompts \
  --reviewed-source
```

The runner refuses to load raw safety prompt text unless those flags are
present. Output files store normalized labels, raw judge response length, and a
hash of the judge response, not raw prompt text.

## Interpretation

Judge labels are secondary annotations. They can support later analysis of
ambiguous outputs, but they are not evidence of provider runtime semantics and
must not be used to claim a provider released, filtered, refused, or settled a
stream at a specific point in time.
