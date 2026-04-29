import sys
from types import SimpleNamespace

from lssa.utils.aws_bedrock import (
    AWS_BEARER_TOKEN_BEDROCK_ENV,
    BedrockRuntimeSdkConfig,
)


def test_bedrock_config_uses_region_from_env() -> None:
    config = BedrockRuntimeSdkConfig.from_env(
        {
            "AWS_REGION": "us-west-2",
            AWS_BEARER_TOKEN_BEDROCK_ENV: "not-printed",
        }
    )

    assert config.region_name == "us-west-2"
    assert config.service_name == "bedrock-runtime"


def test_bedrock_config_defaults_region_without_env() -> None:
    config = BedrockRuntimeSdkConfig.from_env({})

    assert config.region_name == "us-east-1"


def test_bedrock_status_is_redacted() -> None:
    config = BedrockRuntimeSdkConfig.from_env(
        {
            AWS_BEARER_TOKEN_BEDROCK_ENV: "secret-token-value",
        }
    )

    status = config.redacted_status(
        {
            AWS_BEARER_TOKEN_BEDROCK_ENV: "secret-token-value",
        }
    )

    assert status["bearer_token_configured"] is True
    assert "secret-token-value" not in str(status)


def test_bedrock_config_requires_bearer_token_without_printing_value() -> None:
    config = BedrockRuntimeSdkConfig()

    try:
        config.require_bearer_token({})
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("missing bearer token should fail")

    assert AWS_BEARER_TOKEN_BEDROCK_ENV in message
    assert "secret" not in message


def test_bedrock_create_client_uses_lazy_boto3_import(monkeypatch) -> None:
    calls = []

    def fake_client(service_name, *, region_name):
        calls.append((service_name, region_name))
        return {"service_name": service_name, "region_name": region_name}

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=fake_client))

    config = BedrockRuntimeSdkConfig(region_name="us-west-2")
    client = config.create_client(
        {
            AWS_BEARER_TOKEN_BEDROCK_ENV: "not-printed",
        }
    )

    assert client == {"service_name": "bedrock-runtime", "region_name": "us-west-2"}
    assert calls == [("bedrock-runtime", "us-west-2")]
