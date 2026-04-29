# AWS Bedrock SDK Configuration

This document records local SDK configuration for Bedrock Runtime pilots. It
does not authorize safety-signal workloads.

## Credential Variable

Amazon Bedrock API key authentication uses:

```text
AWS_BEARER_TOKEN_BEDROCK
```

Keep this value only in local shell state or `.env`. Do not commit it, print it,
or copy it into trace metadata.

## Region

The default local region is:

```text
AWS_REGION=us-east-1
```

`AWS_DEFAULT_REGION` may also be used by the AWS SDK, but this repository keeps
`AWS_REGION` in `.env.example` to make the intended Bedrock Runtime region
explicit.

## Python SDK

Provider extras install Boto3:

```bash
python -m pip install '.[providers]'
```

The helper in `src/lssa/utils/aws_bedrock.py` prepares a lazy
`bedrock-runtime` client. It checks whether `AWS_BEARER_TOKEN_BEDROCK` exists
without exposing the value.

The provider adapter is:

```text
src/lssa/adapters/aws_bedrock_converse.py
```

It uses Boto3 Bedrock Runtime `converse` and `converse_stream` for benign
raw-provider lifecycle traces. The default benign pilot model is
`amazon.nova-micro-v1:0` because it is a lightweight AWS-hosted model suitable
for harness validation.

Anthropic models on Bedrock may require AWS account-level use-case details to
be submitted and approved before use. That access requirement is separate from
the LSSA adapter and should not be treated as a trace-harness failure.

## Phase Boundary

Real Bedrock API calls still require explicit `--allow-network`. Guardrail
streaming modes, asynchronous filtering, and safety-signal prompts remain out of
scope until a later phase.
