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
from lssa.adapters.openai_responses import OpenAIResponsesAdapter
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
        if not os.environ.get("OPENAI_API_KEY"):
            print("OPENAI_API_KEY is required but was not printed", file=sys.stderr)
            return 2
        print("network execution is prepared but OpenAI SDK client is not wired in this milestone", file=sys.stderr)
        return 2

    print(f"unsupported provider: {args.provider}", file=sys.stderr)
    return 2


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
