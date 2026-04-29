#!/usr/bin/env python3
"""Run or dry-run a small benign raw provider pilot."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.adapters.base import AdapterRequest
from lssa.adapters.openai_responses import OpenAIResponsesAdapter, OpenAIResponsesClient
from lssa.schema.events import ResponseMode
from lssa.tracing.recorder import TraceRecorder
from lssa.tracing.validator import validate_trace

PROMPTS_PATH = ROOT / "src" / "lssa" / "prompts" / "benign_prompts.yaml"
DEFAULT_OUTPUT_DIR = Path("artifacts/real_pilot")
MAX_CALLS_WITHOUT_FORCE = 2
SUPPORTED_PROVIDERS = {"openai_responses"}


@dataclass(frozen=True)
class BenignPrompt:
    prompt_id: str
    category: str
    text: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), required=True)
    parser.add_argument("--prompt-id", default="short_text_generation")
    parser.add_argument("--mode", choices=["streaming", "nonstreaming"], default="streaming")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--paired", action="store_true")
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int, default=128)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    prompts = load_benign_prompts(PROMPTS_PATH)
    if args.prompt_id not in prompts:
        print(f"unknown benign prompt id: {args.prompt_id}", file=sys.stderr)
        return 2
    if args.max_calls > MAX_CALLS_WITHOUT_FORCE and not args.force:
        print("max calls exceeds conservative limit; use --force", file=sys.stderr)
        return 2
    if not _is_ignored_output_dir(args.output_dir):
        print(f"output directory is not ignored by git policy: {args.output_dir}", file=sys.stderr)
        return 2

    modes = ["streaming", "nonstreaming"] if args.paired else [args.mode]
    planned_calls = len(modes)
    if planned_calls > args.max_calls:
        print("planned calls exceed --max-calls", file=sys.stderr)
        return 2

    if not args.allow_network:
        print(
            f"dry-run provider={args.provider} prompt_id={args.prompt_id} "
            f"modes={','.join(modes)} calls={planned_calls} network=disabled"
        )
        return 0

    if args.provider == "openai_responses":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY is required but was not printed", file=sys.stderr)
            return 2
        return _run_openai_network_pilot(args, prompts[args.prompt_id], modes, api_key)

    print(f"unsupported provider: {args.provider}", file=sys.stderr)
    return 2


def _run_openai_network_pilot(
    args: argparse.Namespace,
    prompt: BenignPrompt,
    modes: list[str],
    api_key: str,
) -> int:
    client = OpenAIResponsesClient(
        api_key=api_key,
        timeout_seconds=args.timeout_seconds,
        temperature=args.temperature,
    )
    adapter = OpenAIResponsesAdapter(client=client)
    failures = 0
    for mode_name in modes:
        response_mode = _response_mode(mode_name)
        request = AdapterRequest(
            trace_id=f"openai-responses-{mode_name}-{uuid4().hex}",
            prompt_id=prompt.prompt_id,
            prompt=prompt.text,
            response_mode=response_mode,
            model=args.model,
            provider_family=adapter.provider_family,
            api_surface=adapter.api_surface,
            max_output_tokens=args.max_output_tokens,
            metadata={
                "pilot": "p2_m2_real_benign",
                "mode": mode_name,
            },
        )
        try:
            events = list(adapter.run(request))
        except Exception as exc:  # noqa: BLE001 - CLI must suppress provider tracebacks.
            print(
                f"provider=openai_responses mode={mode_name} status=error "
                f"error_type={type(exc).__name__}",
                file=sys.stderr,
            )
            failures += 1
            continue

        validation = validate_trace(events)
        recorder = TraceRecorder(
            trace_id=request.trace_id,
            provider_family=adapter.provider_family,
            api_surface=adapter.api_surface,
            model=request.model,
            response_mode=response_mode,
        )
        recorder.extend(events)
        run_dir = args.output_dir / "openai_responses" / request.prompt_id / mode_name
        trace_path = recorder.write_jsonl(run_dir / f"{request.trace_id}.jsonl")
        summary_path = recorder.write_summary_json(run_dir / f"{request.trace_id}.summary.json")
        status = "ok" if validation.ok else "invalid"
        if not validation.ok:
            failures += 1
        print(
            f"provider=openai_responses mode={mode_name} status={status} "
            f"events={len(events)} trace={trace_path} summary={summary_path}"
        )
    return 1 if failures else 0


def load_benign_prompts(path: Path = PROMPTS_PATH) -> dict[str, BenignPrompt]:
    prompts: dict[str, BenignPrompt] = {}
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line == "prompts:":
            continue
        if raw_line.startswith("  - id: "):
            if current is not None:
                prompt = _prompt_from_mapping(current)
                prompts[prompt.prompt_id] = prompt
            current = {"id": raw_line.split(": ", 1)[1].strip()}
            continue
        if current is None:
            raise ValueError(f"unexpected prompt line: {raw_line}")
        if raw_line.startswith("    ") and ": " in raw_line:
            key, value = raw_line.strip().split(": ", 1)
            current[key] = value.strip()
            continue
        raise ValueError(f"unsupported prompt line: {raw_line}")
    if current is not None:
        prompt = _prompt_from_mapping(current)
        prompts[prompt.prompt_id] = prompt
    return prompts


def run_fake_openai_pilot(
    *,
    prompt: BenignPrompt,
    mode: ResponseMode,
    raw_events_or_response,
    output_dir: Path,
    model: str = "fake-openai-model",
) -> tuple[bool, Path, Path]:
    request = AdapterRequest(
        trace_id=f"real-pilot-fake-{uuid4().hex}",
        prompt_id=prompt.prompt_id,
        prompt=prompt.text,
        response_mode=mode,
        model=model,
        provider_family="OpenAI",
        api_surface="Responses API",
        max_output_tokens=128,
    )
    adapter = OpenAIResponsesAdapter()
    if mode == ResponseMode.STREAMING:
        events = adapter.map_streaming_events(request, raw_events_or_response)
    else:
        events = adapter.map_nonstreaming_response(request, raw_events_or_response)
    validation = validate_trace(events)
    recorder = TraceRecorder(
        trace_id=request.trace_id,
        provider_family="OpenAI",
        api_surface="Responses API",
        model=model,
        response_mode=mode,
    )
    recorder.extend(events)
    run_dir = output_dir / request.trace_id
    trace_path = recorder.write_jsonl(run_dir / "trace.jsonl")
    summary_path = recorder.write_summary_json(run_dir / "summary.json")
    return validation.ok, trace_path, summary_path


def _response_mode(mode_name: str) -> ResponseMode:
    if mode_name == "streaming":
        return ResponseMode.STREAMING
    if mode_name == "nonstreaming":
        return ResponseMode.NON_STREAMING
    raise ValueError(f"unsupported mode: {mode_name}")


def _prompt_from_mapping(data: dict[str, str]) -> BenignPrompt:
    return BenignPrompt(
        prompt_id=data["id"],
        category=data["category"],
        text=data["text"],
    )


def _is_ignored_output_dir(path: Path) -> bool:
    parts = path.parts
    return bool(parts) and parts[0] == "artifacts"


if __name__ == "__main__":
    sys.exit(main())
