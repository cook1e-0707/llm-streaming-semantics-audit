# Real API Data Policy

This policy applies to future real benign provider pilots.

## Secrets

API keys, `.env`, credentials, private key files, and provider secrets must not
be committed, printed, or included in trace metadata. Scripts may check whether a
required environment variable exists, but must not display its value.

Real pilot scripts expect required keys to already be present in the process
environment. Load `.env` in the shell before running, and do not pass secrets as
command-line arguments.

Bedrock API key authentication uses `AWS_BEARER_TOKEN_BEDROCK`. The repository
may check whether this variable is configured, but must not print or persist the
token value.

Xiaomi MiMo compatible API authentication uses `XIAOMI_MIMO_API_KEY`, with
`MIMO_API_KEY` accepted as a local compatibility fallback. The repository may
record which environment variable name was required, but must not print or
persist the key value.

## Prompt Scope

Only prompt IDs from `src/lssa/prompts/benign_prompts.yaml` are allowed. Unsafe,
borderline, jailbreak, prompt-injection, benchmark, or safety-evaluation prompts
are forbidden in Phase 2.

## Payload Retention

Adapters should preserve raw event type names and concise payload summaries in
event metadata. Full raw provider payloads are not required for Phase 2 and
should be redacted by default. Real pilot artifacts also redact normalized text
`content` by default; retain content only through an explicit future policy
change.

## Artifact Retention

Real pilot artifacts must be written under ignored output directories such as
`artifacts/real_pilot/`. Large trace dumps, raw datasets, and provider outputs
must not be tracked by git.

## Cost Controls

Real pilot scripts must require explicit `--allow-network`, conservative
`--max-calls`, small `--max-output-tokens`, and request timeouts. The default
mode is dry-run.

## Rate Limits and Provider Terms

Real pilots should use minimal calls, respect provider rate limits, and comply
with provider terms. Retries should be conservative and visible in trace
metadata when added.
