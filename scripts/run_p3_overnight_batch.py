#!/usr/bin/env python3
"""Run or dry-run a guarded Phase 3 overnight safety batch."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from .check_judge_ready import check_judge_ready
    from .check_p3_safety_pilot_ready import check_p3_safety_pilot_ready
except ImportError:
    from check_judge_ready import check_judge_ready
    from check_p3_safety_pilot_ready import check_p3_safety_pilot_ready

SUPPORTED_PROVIDERS = (
    "openai_responses",
    "anthropic_messages",
    "aws_bedrock_converse",
    "xiaomi_mimo_openai",
    "xiaomi_mimo_anthropic",
)
SUPPORTED_MODES = ("streaming", "nonstreaming")
SUPPORTED_JUDGE_PROFILES = ("a", "b", "all")
DEFAULT_OUTPUT_ROOT = Path("artifacts/p3_overnight")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", default=",".join(SUPPORTED_PROVIDERS))
    parser.add_argument("--modes", default=",".join(SUPPORTED_MODES))
    parser.add_argument("--prompt-root", type=Path)
    parser.add_argument("--source-glob", default="*.jsonl")
    parser.add_argument("--limit-per-provider-mode", type=int, default=10)
    parser.add_argument("--sample-strategy", choices=["first", "stratified"], default="first")
    parser.add_argument("--sample-seed", type=int, default=0)
    parser.add_argument("--judge-limit", type=int, default=10)
    parser.add_argument("--judge-profile", choices=SUPPORTED_JUDGE_PROFILES, default="all")
    parser.add_argument("--judge-responses", action="store_true")
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--aws-region")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-safety-prompts", action="store_true")
    parser.add_argument("--allow-judge-network", action="store_true")
    parser.add_argument("--reviewed-source", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)

    providers = _expand_csv(args.providers, SUPPORTED_PROVIDERS)
    modes = _expand_csv(args.modes, SUPPORTED_MODES)
    if args.limit_per_provider_mode < 1:
        print("--limit-per-provider-mode must be positive", file=sys.stderr)
        return 2
    if args.judge_limit < 0:
        print("--judge-limit must be non-negative", file=sys.stderr)
        return 2
    if args.limit_per_provider_mode > 3 and not args.force:
        print("large safety batch requires --force after review", file=sys.stderr)
        return 2
    if args.judge_limit > 3 and not args.force:
        print("large judge batch requires --force after review", file=sys.stderr)
        return 2
    if not _is_ignored_output_dir(args.output_root):
        print("--output-root must be under ignored artifacts/", file=sys.stderr)
        return 2

    safety_ready = check_p3_safety_pilot_ready(ROOT, args.prompt_root)
    if not safety_ready.ready:
        failed = ", ".join(check.name for check in safety_ready.checks if not check.ok)
        print(f"P3 safety pilot readiness failed: {failed}", file=sys.stderr)
        return 1
    if args.judge_limit or args.judge_responses:
        judge_ready = check_judge_ready(ROOT, args.prompt_root)
        if not judge_ready.ready:
            failed = ", ".join(check.name for check in judge_ready.checks if not check.ok)
            print(f"judge readiness failed: {failed}", file=sys.stderr)
            return 1

    run_id = args.run_id or datetime.now(timezone.utc).strftime("p3-%Y%m%dT%H%M%SZ")
    run_root = args.output_root / run_id
    logs_dir = run_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    tasks = _build_tasks(args, providers, modes, run_root)
    manifest_path = _write_manifest(run_root, args, providers, modes, tasks)
    failures = 0
    for task in tasks:
        exit_code = _run_task(task, logs_dir)
        if exit_code:
            failures += 1
        print(
            f"p3_task={task['name']} status={'ok' if exit_code == 0 else 'failed'} "
            f"exit_code={exit_code} log={task['log_name']}"
        )

    summary_path = _write_summary(run_root)
    print(
        f"p3_overnight run_id={run_id} dry_run={not args.allow_network} "
        f"tasks={len(tasks)} failures={failures} manifest={manifest_path} summary={summary_path}"
    )
    return 1 if failures else 0


def _build_tasks(
    args: argparse.Namespace,
    providers: list[str],
    modes: list[str],
    run_root: Path,
) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    for provider in providers:
        for mode in modes:
            name = f"safety_{provider}_{mode}"
            command = _safety_command(args, provider, mode, run_root)
            tasks.append({"name": name, "command": command, "log_name": f"{name}.log"})
    if args.judge_limit:
        command = _judge_command(args, run_root)
        tasks.append({"name": "judge_adjudication", "command": command, "log_name": "judge_adjudication.log"})
    return tasks


def _safety_command(
    args: argparse.Namespace,
    provider: str,
    mode: str,
    run_root: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_safety_signal_pilot.py"),
        "--provider",
        provider,
        "--mode",
        mode,
        "--source-glob",
        args.source_glob,
        "--limit",
        str(args.limit_per_provider_mode),
        "--sample-strategy",
        args.sample_strategy,
        "--sample-seed",
        str(args.sample_seed),
        "--max-calls",
        str(args.limit_per_provider_mode),
        "--max-output-tokens",
        str(args.max_output_tokens),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--temperature",
        str(args.temperature),
        "--plan-dir",
        str(run_root / "plans" / "safety_signal"),
        "--output-dir",
        str(run_root / "safety_signal"),
    ]
    if args.prompt_root is not None:
        command.extend(["--prompt-root", str(args.prompt_root)])
    if args.aws_region:
        command.extend(["--aws-region", args.aws_region])
    if args.force:
        command.append("--force")
    if args.allow_network:
        command.append("--allow-network")
    if args.allow_safety_prompts:
        command.append("--allow-safety-prompts")
    if args.judge_responses:
        command.extend(
            [
                "--judge-responses",
                "--judge-profile",
                args.judge_profile,
                "--response-judge-output-dir",
                str(run_root / "response_judge"),
            ]
        )
    if args.allow_judge_network:
        command.append("--allow-judge-network")
    if args.reviewed_source:
        command.append("--reviewed-source")
    return command


def _judge_command(args: argparse.Namespace, run_root: Path) -> list[str]:
    judge_calls = args.judge_limit
    if args.judge_profile == "all":
        judge_calls *= 2
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_judge_adjudication.py"),
        "--source-glob",
        args.source_glob,
        "--limit",
        str(args.judge_limit),
        "--sample-strategy",
        args.sample_strategy,
        "--sample-seed",
        str(args.sample_seed),
        "--max-calls",
        str(judge_calls),
        "--judge-profile",
        args.judge_profile,
        "--plan-dir",
        str(run_root / "plans" / "judge"),
        "--output-dir",
        str(run_root / "judge_adjudication"),
    ]
    if args.prompt_root is not None:
        command.extend(["--prompt-root", str(args.prompt_root)])
    if args.allow_judge_network:
        command.append("--allow-judge-network")
    if args.allow_safety_prompts:
        command.append("--allow-safety-prompts")
    if args.reviewed_source:
        command.append("--reviewed-source")
    return command


def _run_task(task: dict[str, object], logs_dir: Path) -> int:
    log_path = logs_dir / str(task["log_name"])
    command = [str(part) for part in task["command"]]
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(command) + "\n")
        handle.flush()
        proc = subprocess.run(
            command,
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return proc.returncode


def _write_manifest(
    run_root: Path,
    args: argparse.Namespace,
    providers: list[str],
    modes: list[str],
    tasks: list[dict[str, object]],
) -> Path:
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / "manifest.json"
    payload = {
        "run_id": run_root.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "modes": modes,
        "source_glob": args.source_glob,
        "sample_strategy": args.sample_strategy,
        "sample_seed": args.sample_seed,
        "limit_per_provider_mode": args.limit_per_provider_mode,
        "judge_limit": args.judge_limit,
        "judge_profile": args.judge_profile,
        "judge_responses": args.judge_responses,
        "max_output_tokens": args.max_output_tokens,
        "timeout_seconds": args.timeout_seconds,
        "temperature": args.temperature,
        "allow_network": args.allow_network,
        "allow_safety_prompts": args.allow_safety_prompts,
        "allow_judge_network": args.allow_judge_network,
        "reviewed_source": args.reviewed_source,
        "raw_text_committed": False,
        "tasks": [
            {
                "name": task["name"],
                "command": task["command"],
                "log_name": task["log_name"],
            }
            for task in tasks
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_summary(run_root: Path) -> Path:
    summary = {
        "run_id": run_root.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_text_committed": False,
        "safety_trace_count": 0,
        "judge_result_count": 0,
        "response_judge_result_count": 0,
        "trace_terminal_reasons": {},
        "event_terminal_reason_counts": {},
        "terminal_reasons": {},
        "provider_stop_reasons": {},
        "event_type_counts": {},
        "safety_signal_event_count": 0,
        "safety_signal_event_types": {},
        "judge_labels": {},
        "response_judge_labels": {},
    }
    trace_terminal_reasons: Counter[str] = Counter()
    event_terminal_reason_counts: Counter[str] = Counter()
    provider_stop_reasons: Counter[str] = Counter()
    event_type_counts: Counter[str] = Counter()
    safety_signal_event_types: Counter[str] = Counter()
    judge_labels: Counter[str] = Counter()
    response_judge_labels: Counter[str] = Counter()

    for path in sorted((run_root / "safety_signal").rglob("*.summary.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary["safety_trace_count"] += 1
        trace_terminal_reasons[str(payload.get("terminal_reason") or "unknown")] += 1
        for event in payload.get("events", []):
            if not isinstance(event, dict):
                continue
            event_type_counts[str(event.get("event_type") or "unknown")] += 1
            terminal_reason = event.get("terminal_reason")
            if terminal_reason is not None:
                event_terminal_reason_counts[str(terminal_reason)] += 1
            event_type = str(event.get("event_type") or "unknown")
            if event_type in {"safety_annotation", "refusal", "content_filter"}:
                safety_signal_event_types[event_type] += 1
            if event.get("event_type") == "final_response":
                metadata = event.get("metadata") or {}
                if isinstance(metadata, dict):
                    provider_stop_reasons[str(metadata.get("provider_stop_reason") or "unknown")] += 1

    for path in sorted((run_root / "judge_adjudication").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary["judge_result_count"] += 1
        judge_labels[str(payload.get("label") or "unknown")] += 1

    for path in sorted((run_root / "response_judge").rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary["response_judge_result_count"] += 1
        response_judge_labels[str(payload.get("label") or "unknown")] += 1

    summary["trace_terminal_reasons"] = dict(sorted(trace_terminal_reasons.items()))
    summary["event_terminal_reason_counts"] = dict(sorted(event_terminal_reason_counts.items()))
    summary["terminal_reasons"] = dict(sorted(trace_terminal_reasons.items()))
    summary["provider_stop_reasons"] = dict(sorted(provider_stop_reasons.items()))
    summary["event_type_counts"] = dict(sorted(event_type_counts.items()))
    summary["safety_signal_event_count"] = sum(safety_signal_event_types.values())
    summary["safety_signal_event_types"] = dict(sorted(safety_signal_event_types.items()))
    summary["judge_labels"] = dict(sorted(judge_labels.items()))
    summary["response_judge_labels"] = dict(sorted(response_judge_labels.items()))
    path = run_root / "p3_overnight_summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _expand_csv(value: str, allowed: tuple[str, ...]) -> list[str]:
    if value == "all":
        return list(allowed)
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    unsupported = [item for item in parsed if item not in allowed]
    if unsupported:
        raise SystemExit(f"unsupported values: {', '.join(unsupported)}")
    return parsed


def _is_ignored_output_dir(path: Path) -> bool:
    if path.is_absolute():
        try:
            path = path.relative_to(ROOT)
        except ValueError:
            return False
    parts = path.parts
    return bool(parts) and parts[0] == "artifacts"


if __name__ == "__main__":
    sys.exit(main())
