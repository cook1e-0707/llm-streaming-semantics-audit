# Phase 1 Readiness Quality Gate

The Phase 1 quality gate determines whether the repository is ready to move from
provider documentation audit to a raw API benign pilot.

The gate does not authorize safety-signal experiments, unsafe prompts, provider
adapter migration, framework propagation studies, or old result migration. It
only checks that the documentation evidence layer is strong enough to serve as a
baseline for Phase 2 harness design.

## Why This Gate Exists

Phase 1 provides the public contract baseline: what each provider or framework
officially documents about release, validation, safety signal, refusal,
settlement, and client obligations. Phase 2 should measure black-box behavior
against that baseline, not retroactively search for documentation after seeing
experimental traces.

## Readiness Means

The repository is Phase 1 ready when:

- `docs/provider_evidence.yaml` exists and is parseable;
- every required provider family has at least one official source entry;
- every required source field is present and non-blank;
- every non-deferred provider family has at least one extracted claim;
- `docs/provider_matrix.md` is generated and up to date;
- provider matrix cells are non-blank;
- unknown semantics are explicit;
- every non-unknown matrix field is backed by evidence;
- Phase 2 core metrics exist in `docs/metrics_registry.yaml`;
- no forbidden local data, secrets, or result directories are tracked by git.

## Out of Scope

The quality gate does not check runtime provider behavior. It does not call
OpenAI, Azure, AWS, Anthropic, Google, or any other model provider API. It does
not validate unsafe prompts or policy coverage.

## Phase 2 Allowed Work

After this gate passes, Phase 2 may add a benign-only raw API pilot harness that
records request, first-byte, first-token, chunk, terminal, iterator, and
settlement events.

## Phase 2 Still Forbidden

Phase 2 remains forbidden from:

- adding unsafe prompts;
- importing benchmark prompt datasets;
- migrating legacy raw results;
- running safety-signal experiments;
- studying agent frameworks as provider ground truth;
- collapsing provider, SDK, framework, application, and user-visible layers.

Run the gate with:

```bash
python scripts/check_phase1_ready.py
python scripts/check_phase1_ready.py --json
```
