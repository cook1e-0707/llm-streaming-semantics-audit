"""AWS Bedrock SDK configuration helpers.

This module only prepares local SDK configuration. It does not call Bedrock.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

AWS_BEARER_TOKEN_BEDROCK_ENV = "AWS_BEARER_TOKEN_BEDROCK"
AWS_REGION_ENV = "AWS_REGION"
AWS_DEFAULT_REGION_ENV = "AWS_DEFAULT_REGION"
DEFAULT_BEDROCK_REGION = "us-east-1"
BEDROCK_RUNTIME_SERVICE = "bedrock-runtime"


@dataclass(frozen=True)
class BedrockRuntimeSdkConfig:
    """Configuration for a lazy Boto3 Bedrock Runtime client."""

    region_name: str = DEFAULT_BEDROCK_REGION
    service_name: str = BEDROCK_RUNTIME_SERVICE
    bearer_token_env_var: str = AWS_BEARER_TOKEN_BEDROCK_ENV

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "BedrockRuntimeSdkConfig":
        env = os.environ if environ is None else environ
        region = (
            env.get(AWS_REGION_ENV)
            or env.get(AWS_DEFAULT_REGION_ENV)
            or DEFAULT_BEDROCK_REGION
        )
        return cls(region_name=region)

    def has_bearer_token(self, environ: Mapping[str, str] | None = None) -> bool:
        env = os.environ if environ is None else environ
        return bool(env.get(self.bearer_token_env_var))

    def require_bearer_token(self, environ: Mapping[str, str] | None = None) -> None:
        if not self.has_bearer_token(environ):
            raise RuntimeError(
                f"{self.bearer_token_env_var} is required but must not be printed"
            )

    def redacted_status(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, str | bool]:
        return {
            "service_name": self.service_name,
            "region_name": self.region_name,
            "bearer_token_env_var": self.bearer_token_env_var,
            "bearer_token_configured": self.has_bearer_token(environ),
        }

    def create_client(self, environ: Mapping[str, str] | None = None) -> Any:
        """Create a Boto3 Bedrock Runtime client without exposing the token."""

        self.require_bearer_token(environ)
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "boto3 package is not installed; run python -m pip install '.[providers]'"
            ) from exc
        return boto3.client(self.service_name, region_name=self.region_name)
