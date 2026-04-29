"""Constrained manifest parser for benign batch pilot planning."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ALLOWED_MODES = {"streaming", "nonstreaming"}


@dataclass(frozen=True)
class BenignBatchManifest:
    title: str
    providers: tuple[str, ...]
    prompt_ids: tuple[str, ...]
    modes: tuple[str, ...]
    repetitions: int
    max_output_tokens: int
    timeout_seconds: int
    temperature: float
    max_total_calls_without_force: int


@dataclass(frozen=True)
class PlannedRun:
    provider: str
    prompt_id: str
    mode: str
    repetition: int
    max_output_tokens: int
    timeout_seconds: int
    temperature: float

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "prompt_id": self.prompt_id,
            "mode": self.mode,
            "repetition": self.repetition,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
        }


def load_benign_batch_manifest(path: Path) -> BenignBatchManifest:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    required = {
        "title",
        "providers",
        "prompt_ids",
        "modes",
        "repetitions",
        "max_output_tokens",
        "timeout_seconds",
        "temperature",
        "max_total_calls_without_force",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"manifest missing keys: {sorted(missing)}")

    manifest = BenignBatchManifest(
        title=str(data["title"]),
        providers=tuple(_as_nonempty_string_list(data["providers"], "providers")),
        prompt_ids=tuple(_as_nonempty_string_list(data["prompt_ids"], "prompt_ids")),
        modes=tuple(_as_nonempty_string_list(data["modes"], "modes")),
        repetitions=int(data["repetitions"]),
        max_output_tokens=int(data["max_output_tokens"]),
        timeout_seconds=int(data["timeout_seconds"]),
        temperature=float(data["temperature"]),
        max_total_calls_without_force=int(data["max_total_calls_without_force"]),
    )
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: BenignBatchManifest) -> None:
    unsupported_modes = sorted(set(manifest.modes) - ALLOWED_MODES)
    if unsupported_modes:
        raise ValueError(f"unsupported modes: {unsupported_modes}")
    if manifest.repetitions < 1:
        raise ValueError("repetitions must be positive")
    if manifest.max_output_tokens < 1:
        raise ValueError("max_output_tokens must be positive")
    if manifest.timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    if manifest.max_total_calls_without_force < 1:
        raise ValueError("max_total_calls_without_force must be positive")


def build_planned_runs(manifest: BenignBatchManifest) -> list[PlannedRun]:
    runs: list[PlannedRun] = []
    for provider in manifest.providers:
        for prompt_id in manifest.prompt_ids:
            for mode in manifest.modes:
                for repetition in range(1, manifest.repetitions + 1):
                    runs.append(
                        PlannedRun(
                            provider=provider,
                            prompt_id=prompt_id,
                            mode=mode,
                            repetition=repetition,
                            max_output_tokens=manifest.max_output_tokens,
                            timeout_seconds=manifest.timeout_seconds,
                            temperature=manifest.temperature,
                        )
                    )
    return runs


def _as_nonempty_string_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a non-empty list")
    result = [str(item).strip() for item in value]
    if any(not item for item in result):
        raise ValueError(f"{key} contains an empty item")
    return result
