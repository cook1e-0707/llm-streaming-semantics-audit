#!/usr/bin/env python3
"""Run or dry-run optional NVIDIA guard-model adjudication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.judging.nvidia import (
    NVIDIA_JUDGE_PROVIDER,
    SUPPORTED_NVIDIA_JUDGE_PROFILES,
    NvidiaGuardJudge,
    NvidiaJudgeConfig,
)
from lssa.prompts.safety_external import iter_safety_prompt_records, resolve_safety_prompt_root

DEFAULT_PLAN_DIR = Path("artifacts/judge_plans")
DEFAULT_OUTPUT_DIR = Path("artifacts/judge_adjudication")
JUDGE_PROFILE_CHOICES = (*SUPPORTED_NVIDIA_JUDGE_PROFILES, "all")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-root", type=Path)
    parser.add_argument("--source-glob", default="*.jsonl")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--judge-profile", choices=JUDGE_PROFILE_CHOICES, default="a")
    parser.add_argument("--allow-judge-network", action="store_true")
    parser.add_argument("--allow-safety-prompts", action="store_true")
    parser.add_argument("--reviewed-source", action="store_true")
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    if args.limit < 1 or args.max_calls < 1:
        print("--limit and --max-calls must be positive", file=sys.stderr)
        return 2
    if args.limit > args.max_calls:
        print("planned judge calls exceed --max-calls", file=sys.stderr)
        return 2
    if not _is_ignored_output_dir(args.plan_dir) or not _is_ignored_output_dir(args.output_dir):
        print("plan/output directories must be under ignored artifacts/", file=sys.stderr)
        return 2

    include_text = (
        args.allow_judge_network
        and args.allow_safety_prompts
        and args.reviewed_source
    )
    try:
        root = resolve_safety_prompt_root(args.prompt_root)
        records = iter_safety_prompt_records(
            root,
            include_text=include_text,
            limit=args.limit,
            source_glob=args.source_glob,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not records:
        print(f"no loadable safety prompts found under {root}", file=sys.stderr)
        return 1

    configs = _configs_for_profile(args.judge_profile)
    planned_calls = len(records) * len(configs)
    if planned_calls > args.max_calls:
        print("planned judge calls exceed --max-calls", file=sys.stderr)
        return 2

    plan_path = _write_plan(args.plan_dir, root, records, configs, planned_calls, args)
    if not args.allow_judge_network:
        models = ",".join(f"{config.profile}:{config.model}" for config in configs)
        print(
            f"dry-run judge_provider={NVIDIA_JUDGE_PROVIDER} profiles={args.judge_profile} "
            f"models={models} planned_calls={planned_calls} network=disabled "
            f"safety_prompts_loaded=no plan={plan_path}"
        )
        return 0
    if not args.allow_safety_prompts:
        print("--allow-safety-prompts is required for judge calls over safety prompts", file=sys.stderr)
        return 2
    if not args.reviewed_source:
        print("--reviewed-source is required before judge calls", file=sys.stderr)
        return 2

    for config in configs:
        try:
            config.require_api_key()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    failures = 0
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for config in configs:
        judge = NvidiaGuardJudge(config=config)
        for record in records:
            if record.prompt_text is None:
                failures += 1
                continue
            try:
                result = judge.classify_prompt(
                    prompt_id=record.prompt_id,
                    prompt_text=record.prompt_text,
                )
            except Exception as exc:  # noqa: BLE001 - CLI suppresses provider tracebacks.
                print(
                    f"judge_provider={NVIDIA_JUDGE_PROVIDER} judge_profile={config.profile} "
                    f"status=error prompt_id={record.prompt_id} "
                    f"error_type={type(exc).__name__}",
                    file=sys.stderr,
                )
                failures += 1
                continue
            result_path = output_dir / f"judge-{config.profile}-{uuid4().hex}.json"
            result_path.write_text(
                json.dumps(result.to_redacted_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print(
                f"judge_provider={NVIDIA_JUDGE_PROVIDER} judge_profile={config.profile} "
                f"status=ok prompt_id={record.prompt_id} label={result.label} "
                f"result={result_path}"
            )
    return 1 if failures else 0


def _configs_for_profile(profile: str) -> list[NvidiaJudgeConfig]:
    if profile == "all":
        return [NvidiaJudgeConfig.from_env_profile(item) for item in SUPPORTED_NVIDIA_JUDGE_PROFILES]
    return [NvidiaJudgeConfig.from_env_profile(profile)]


def _write_plan(
    plan_dir: Path,
    root: Path,
    records,
    configs: list[NvidiaJudgeConfig],
    planned_calls: int,
    args: argparse.Namespace,
) -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"judge-plan-{uuid4().hex}.json"
    payload = {
        "judge_provider": NVIDIA_JUDGE_PROVIDER,
        "judge_profile": args.judge_profile,
        "judge_base_url": configs[0].base_url,
        "judges": [
            {
                "judge_profile": config.profile,
                "judge_model": config.model,
                "judge_api_key_env": config.api_key_env,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
            }
            for config in configs
        ],
        "prompt_root": str(root),
        "planned_calls": planned_calls,
        "allow_judge_network": args.allow_judge_network,
        "allow_safety_prompts": args.allow_safety_prompts,
        "reviewed_source": args.reviewed_source,
        "raw_text_in_plan": False,
        "records": [record.to_redacted_dict() for record in records],
    }
    for record in payload["records"]:
        record["raw_text_loaded"] = False
    plan_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return plan_path


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
