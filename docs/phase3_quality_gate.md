# Phase 3 Quality Gate

This gate keeps Phase 3 from moving directly from benign lifecycle traces to
real safety-signal provider calls.

## What The Gate Proves

- Phase 2 benign pilot summaries remain reproducible.
- The benign lifecycle comparison remains reproducible.
- P3.M1 policy documents exist.
- The safety prompt registry example is redacted.
- The mock safety-signal harness can validate synthetic delayed annotation,
  refusal, and content-filter traces.
- P3.M2 remains blocked until a reviewer approves prompt sourcing, category
  labels, external storage, retention rules, and stop conditions.

## What The Gate Does Not Authorize

- real safety-signal API calls
- raw unsafe prompt text in git
- jailbreak benchmark imports
- framework propagation experiments
- provider safety ranking

## Command

```bash
python scripts/check_phase3_ready.py
python scripts/check_p3_mock_safety_ready.py
python scripts/check_phase3_ready.py --json
```

The script exits successfully when the policy gate is healthy and P3.M2 remains
intentionally blocked.
