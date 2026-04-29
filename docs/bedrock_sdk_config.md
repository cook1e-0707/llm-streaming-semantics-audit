# AWS Bedrock SDK Configuration

This document records local SDK configuration for future Bedrock Runtime pilots.
It does not authorize Bedrock experiments or safety-signal workloads.

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

## Phase Boundary

This is configuration only. Bedrock provider adapters, real Bedrock API calls,
guardrail streaming modes, and safety-signal prompts remain out of scope until
the project explicitly opens a Bedrock pilot milestone.
