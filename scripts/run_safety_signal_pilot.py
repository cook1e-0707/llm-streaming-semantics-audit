#!/usr/bin/env python3
"""Run or dry-run a guarded Phase 3 safety-signal pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.adapters.anthropic_messages import AnthropicMessagesAdapter, AnthropicMessagesClient
from lssa.adapters.aws_bedrock_converse import AwsBedrockConverseAdapter, AwsBedrockConverseClient
from lssa.adapters.base import AdapterRequest
from lssa.adapters.openai_responses import OpenAIResponsesAdapter, OpenAIResponsesClient
from lssa.judging.nvidia import (
    NVIDIA_JUDGE_PROVIDER,
    SUPPORTED_NVIDIA_JUDGE_PROFILES,
    NvidiaGuardJudge,
    NvidiaJudgeConfig,
)
from lssa.prompts.safety_external import (
    SAFETY_PROMPT_ROOT_ENV,
    SafetyPromptRecord,
    iter_safety_prompt_records,
    resolve_safety_prompt_root,
)
from lssa.schema.events import EventType, ResponseMode, StreamEvent, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from lssa.tracing.validator import validate_trace
from lssa.utils.aws_bedrock import AWS_BEARER_TOKEN_BEDROCK_ENV, BedrockRuntimeSdkConfig

DEFAULT_OUTPUT_DIR = Path("artifacts/safety_signal_pilot")
DEFAULT_PLAN_DIR = Path("artifacts/safety_signal_plans")
DEFAULT_RESPONSE_JUDGE_OUTPUT_DIR = Path("artifacts/response_judge")
JUDGE_PROFILE_CHOICES = (*SUPPORTED_NVIDIA_JUDGE_PROFILES, "all")
SUPPORTED_PROVIDERS = {
    "anthropic_messages",
    "aws_bedrock_converse",
    "openai_responses",
}
DEFAULT_MODELS = {
    "anthropic_messages": "claude-haiku-4-5-20251001",
    "aws_bedrock_converse": "amazon.nova-micro-v1:0",
    "openai_responses": "gpt-4.1-mini",
}
MAX_CALLS_WITHOUT_FORCE = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), required=True)
    parser.add_argument("--mode", choices=["streaming", "nonstreaming"], default="streaming")
    parser.add_argument("--model")
    parser.add_argument("--prompt-root", type=Path)
    parser.add_argument("--source-glob", default="*.jsonl")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--aws-region")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-safety-prompts", action="store_true")
    parser.add_argument("--judge-responses", action="store_true")
    parser.add_argument("--judge-profile", choices=JUDGE_PROFILE_CHOICES, default="all")
    parser.add_argument("--allow-judge-network", action="store_true")
    parser.add_argument("--reviewed-source", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--response-judge-output-dir",
        type=Path,
        default=DEFAULT_RESPONSE_JUDGE_OUTPUT_DIR,
    )
    args = parser.parse_args(argv)

    if args.limit < 1:
        print("--limit must be positive", file=sys.stderr)
        return 2
    if args.max_calls < 1:
        print("--max-calls must be positive", file=sys.stderr)
        return 2
    if args.limit > args.max_calls:
        print("planned safety calls exceed --max-calls", file=sys.stderr)
        return 2
    if args.max_calls > MAX_CALLS_WITHOUT_FORCE and not args.force:
        print("safety max calls exceeds conservative limit; use --force after review", file=sys.stderr)
        return 2
    if (
        not _is_ignored_output_dir(args.plan_dir)
        or not _is_ignored_output_dir(args.output_dir)
        or not _is_ignored_output_dir(args.response_judge_output_dir)
    ):
        print("plan/output directories must be under ignored artifacts/", file=sys.stderr)
        return 2
    if args.judge_responses and args.allow_judge_network and not args.allow_network:
        print("--judge-responses requires provider --allow-network", file=sys.stderr)
        return 2

    try:
        root = resolve_safety_prompt_root(args.prompt_root)
        records = iter_safety_prompt_records(
            root,
            include_text=(
                args.allow_network
                and args.allow_safety_prompts
                and args.reviewed_source
            ),
            limit=args.limit,
            source_glob=args.source_glob,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not records:
        print(f"no loadable safety prompts found under {root}", file=sys.stderr)
        return 1

    plan_path = _write_redacted_plan(args, root, records)
    if not args.allow_network:
        print(
            f"dry-run safety_provider={args.provider} mode={args.mode} "
            f"planned_calls={len(records)} network=disabled "
            f"safety_prompts_loaded=no plan={plan_path}"
        )
        return 0
    if not args.allow_safety_prompts:
        print("--allow-safety-prompts is required for safety prompt network calls", file=sys.stderr)
        return 2
    if not args.reviewed_source:
        print("--reviewed-source is required before safety prompt network calls", file=sys.stderr)
        return 2
    if args.judge_responses and not args.allow_judge_network:
        print("--allow-judge-network is required for response-level judge calls", file=sys.stderr)
        return 2

    try:
        return _run_network_pilot(args, records)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _run_network_pilot(
    args: argparse.Namespace,
    records: list[SafetyPromptRecord],
) -> int:
    adapter = _adapter_for_provider(args)
    judge_configs = _judge_configs_for_profile(args.judge_profile) if args.judge_responses else []
    for config in judge_configs:
        config.require_api_key()
    judges = [NvidiaGuardJudge(config=config) for config in judge_configs]
    failures = 0
    for record in records:
        if record.prompt_text is None:
            print(f"prompt text was not loaded for {record.prompt_id}", file=sys.stderr)
            failures += 1
            continue
        response_mode = _response_mode(args.mode)
        request = AdapterRequest(
            trace_id=f"safety-{args.provider}-{args.mode}-{uuid4().hex}",
            prompt_id=record.prompt_id,
            prompt=record.prompt_text,
            response_mode=response_mode,
            model=_model_for_provider(args),
            provider_family=adapter.provider_family,
            api_surface=adapter.api_surface,
            max_output_tokens=args.max_output_tokens,
            metadata={
                "pilot": "p3_safety_signal",
                "mode": args.mode,
                "source_file": record.source_file,
                "source_line": str(record.line_number),
                "category": record.category,
                "benchmark": record.benchmark,
                "language": record.language,
            },
        )
        try:
            events = list(adapter.run(request))
        except Exception as exc:  # noqa: BLE001 - CLI suppresses provider tracebacks.
            print(
                f"provider={args.provider} mode={args.mode} status=error "
                f"prompt_id={record.prompt_id} error_type={type(exc).__name__}",
                file=sys.stderr,
            )
            failures += 1
            continue
        judge_failure_count = 0
        if judges:
            judge_failure_count = _judge_final_response(
                judges,
                request=request,
                record=record,
                provider_name=args.provider,
                mode_name=args.mode,
                events=events,
                output_dir=args.response_judge_output_dir,
            )
            failures += judge_failure_count
        validation = validate_trace(events)
        recorder = TraceRecorder(
            trace_id=request.trace_id,
            provider_family=adapter.provider_family,
            api_surface=adapter.api_surface,
            model=request.model,
            response_mode=response_mode,
        )
        recorder.extend(events)
        run_dir = args.output_dir / args.provider / _safe_id(record.prompt_id) / args.mode
        trace_path = recorder.write_jsonl(
            run_dir / f"{request.trace_id}.jsonl",
            redact_content=True,
        )
        summary_path = recorder.write_summary_json(
            run_dir / f"{request.trace_id}.summary.json",
            redact_content=True,
        )
        status = _pilot_status(events, validation.ok)
        if status != "ok":
            failures += 1
        print(
            f"provider={args.provider} mode={args.mode} status={status} "
            f"prompt_id={record.prompt_id} events={len(events)} "
            f"response_judge_failures={judge_failure_count} "
            f"trace={trace_path} summary={summary_path}"
        )
    return 1 if failures else 0


def _write_redacted_plan(
    args: argparse.Namespace,
    root: Path,
    records: list[SafetyPromptRecord],
) -> Path:
    args.plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.plan_dir / f"safety-plan-{uuid4().hex}.json"
    payload = {
        "provider": args.provider,
        "mode": args.mode,
        "model": _model_for_provider(args),
        "prompt_root": str(root),
        "planned_calls": len(records),
        "max_output_tokens": args.max_output_tokens,
        "timeout_seconds": args.timeout_seconds,
        "temperature": args.temperature,
        "allow_network": args.allow_network,
        "allow_safety_prompts": args.allow_safety_prompts,
        "judge_responses": args.judge_responses,
        "judge_profile": args.judge_profile,
        "allow_judge_network": args.allow_judge_network,
        "response_judge_output_dir": str(args.response_judge_output_dir),
        "reviewed_source": args.reviewed_source,
        "raw_text_committed": False,
        "raw_provider_output_committed": False,
        "raw_text_in_plan": False,
        "records": [record.to_redacted_dict() for record in records],
    }
    for record in payload["records"]:
        record["raw_text_loaded"] = False
    plan_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return plan_path


def _adapter_for_provider(args: argparse.Namespace):
    if args.provider == "openai_responses":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required but was not printed")
        return OpenAIResponsesAdapter(
            client=OpenAIResponsesClient(
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
                temperature=args.temperature,
            )
        )
    if args.provider == "anthropic_messages":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required but was not printed")
        return AnthropicMessagesAdapter(
            client=AnthropicMessagesClient(
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
                temperature=args.temperature,
            )
        )
    if args.provider == "aws_bedrock_converse":
        if not os.environ.get(AWS_BEARER_TOKEN_BEDROCK_ENV):
            raise RuntimeError(f"{AWS_BEARER_TOKEN_BEDROCK_ENV} is required but was not printed")
        sdk_config = BedrockRuntimeSdkConfig.from_env()
        region_name = args.aws_region or sdk_config.region_name
        return AwsBedrockConverseAdapter(
            client=AwsBedrockConverseClient(
                region_name=region_name,
                temperature=args.temperature,
            )
        )
    raise RuntimeError(f"unsupported provider: {args.provider}")


def _response_mode(mode_name: str) -> ResponseMode:
    if mode_name == "streaming":
        return ResponseMode.STREAMING
    if mode_name == "nonstreaming":
        return ResponseMode.NON_STREAMING
    raise ValueError(f"unsupported mode: {mode_name}")


def _pilot_status(events: list[StreamEvent], validation_ok: bool) -> str:
    if any(event.event_type == EventType.ERROR for event in events):
        return "error"
    if any(event.terminal_reason == TerminalReasonType.ERROR for event in events):
        return "error"
    return "ok" if validation_ok else "invalid"


def _model_for_provider(args: argparse.Namespace) -> str:
    return args.model or DEFAULT_MODELS[args.provider]


def _judge_configs_for_profile(profile: str) -> list[NvidiaJudgeConfig]:
    if profile == "all":
        return [NvidiaJudgeConfig.from_env_profile(item) for item in SUPPORTED_NVIDIA_JUDGE_PROFILES]
    return [NvidiaJudgeConfig.from_env_profile(profile)]


def _judge_final_response(
    judges: list[NvidiaGuardJudge],
    *,
    request: AdapterRequest,
    record: SafetyPromptRecord,
    provider_name: str,
    mode_name: str,
    events: list[StreamEvent],
    output_dir: Path,
) -> int:
    final_response = _final_response_content(events)
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for judge in judges:
        base_payload = {
            "judge_subject": "provider_final_response",
            "judge_provider": NVIDIA_JUDGE_PROVIDER,
            "judge_profile": judge.config.profile,
            "judge_model": judge.config.model,
            "provider": provider_name,
            "mode": mode_name,
            "trace_id": request.trace_id,
            "prompt_id": record.prompt_id,
            "source_file": record.source_file,
            "source_line": record.line_number,
            "benchmark": record.benchmark,
            "category": record.category,
            "language": record.language,
            "raw_prompt_committed": False,
            "raw_provider_output_committed": False,
        }
        result_path = (
            output_dir
            / provider_name
            / _safe_id(record.prompt_id)
            / mode_name
            / f"response-judge-{judge.config.profile}-{uuid4().hex}.json"
        )
        result_path.parent.mkdir(parents=True, exist_ok=True)
        if not final_response:
            payload = dict(base_payload)
            payload.update(
                {
                    "label": "no_output",
                    "response_judge_call_made": False,
                    "raw_provider_output_sha256": None,
                    "raw_provider_output_chars": 0,
                    "raw_response_committed": False,
                }
            )
            result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            print(
                f"response_judge provider={provider_name} mode={mode_name} "
                f"judge_profile={judge.config.profile} status=skipped_no_output "
                f"prompt_id={record.prompt_id} result={result_path}"
            )
            continue
        try:
            result = judge.classify_prompt(
                prompt_id=f"{request.trace_id}:{record.prompt_id}:response",
                prompt_text=final_response,
            )
        except Exception as exc:  # noqa: BLE001 - CLI suppresses provider tracebacks.
            failures += 1
            payload = dict(base_payload)
            payload.update(
                {
                    "label": "judge_error",
                    "response_judge_call_made": True,
                    "error_type": type(exc).__name__,
                    "raw_provider_output_sha256": hashlib.sha256(
                        final_response.encode("utf-8")
                    ).hexdigest(),
                    "raw_provider_output_chars": len(final_response),
                    "raw_response_committed": False,
                }
            )
            result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            print(
                f"response_judge provider={provider_name} mode={mode_name} "
                f"judge_profile={judge.config.profile} status=error "
                f"prompt_id={record.prompt_id} error_type={type(exc).__name__} "
                f"result={result_path}",
                file=sys.stderr,
            )
            continue
        payload = dict(base_payload)
        payload.update(result.to_redacted_dict())
        payload.update(
            {
                "response_judge_call_made": True,
                "raw_provider_output_sha256": hashlib.sha256(
                    final_response.encode("utf-8")
                ).hexdigest(),
                "raw_provider_output_chars": len(final_response),
            }
        )
        result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(
            f"response_judge provider={provider_name} mode={mode_name} "
            f"judge_profile={judge.config.profile} status=ok prompt_id={record.prompt_id} "
            f"label={result.label} result={result_path}"
        )
    return failures


def _final_response_content(events: list[StreamEvent]) -> str | None:
    for event in reversed(events):
        if event.event_type == EventType.FINAL_RESPONSE:
            return event.content
    return None


def _is_ignored_output_dir(path: Path) -> bool:
    if path.is_absolute():
        try:
            path = path.relative_to(ROOT)
        except ValueError:
            return False
    parts = path.parts
    return bool(parts) and parts[0] == "artifacts"


def _safe_id(prompt_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in prompt_id)[:120]


if __name__ == "__main__":
    sys.exit(main())
