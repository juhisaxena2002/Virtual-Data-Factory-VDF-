"""Eval harness for the prompt + tool definition.

Runs ~25 representative prompts against real Gemini and reports pass rate
+ failure reasons. Marked ``eval`` so it doesn't run on every PR — only
nightly in CI, or on demand via ``pytest -m eval``.

Each case has assertions:
  - The spec validates.
  - It contains at least N fields.
  - Optionally, it contains a specific provider / anomaly type / distribution.

Exit criterion: pass rate >= 95% across all cases over 3 trials each.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from synthgen import Client, SynthgenError
from synthgen.backends import GeminiBackend
from synthgen.types import Spec

CASES_PATH = Path(__file__).parent / "cases.jsonl"
TRIALS_PER_CASE = 3


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_case(spec: Spec, case: dict) -> None:
    """Apply the case's optional assertions to a compiled spec."""
    assert len(spec.fields) >= case.get("expected_min_fields", 1), (
        f"Expected at least {case.get('expected_min_fields', 1)} fields, got {len(spec.fields)}"
    )

    if "must_contain_field_with_provider" in case:
        provider = case["must_contain_field_with_provider"]
        assert any(f.provider == provider for f in spec.fields), (
            f"No field with provider {provider!r}. Got providers: {[f.provider for f in spec.fields]}"
        )

    if "must_contain_distribution" in case:
        dist = case["must_contain_distribution"]
        assert any(f.distribution == dist for f in spec.fields), (
            f"No field with distribution {dist!r}. Got distributions: "
            f"{[f.distribution for f in spec.fields]}"
        )

    if "must_contain_anomaly_type" in case:
        anomaly_type = case["must_contain_anomaly_type"]
        all_anomalies = [a.type for f in spec.fields for a in f.anomalies]
        assert anomaly_type in all_anomalies, (
            f"No anomaly of type {anomaly_type!r}. Got anomalies: {all_anomalies}"
        )


# ---------------------------------------------------------------------------
# The eval marker — slow, costs Gemini tokens
# ---------------------------------------------------------------------------
@pytest.mark.eval
@pytest.mark.skipif(
    not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
    reason="Eval requires GOOGLE_API_KEY or GEMINI_API_KEY",
)
def test_prompt_eval_pass_rate() -> None:
    """Run every case three times; require >= 95% pass rate."""
    client = Client(backend=GeminiBackend(), cache=None)
    cases = _load_cases()
    results: Counter[str] = Counter()
    failures: list[dict] = []

    for case in cases:
        for trial in range(TRIALS_PER_CASE):
            try:
                spec = client.compile_spec(case["prompt"])
                _assert_case(spec, case)
                results["pass"] += 1
            except (AssertionError, SynthgenError) as e:
                results["fail"] += 1
                failures.append({"case": case["id"], "trial": trial, "err": str(e)})

    total = results["pass"] + results["fail"]
    pass_rate = results["pass"] / total if total else 0.0

    # Write a results report so prompt changes are auditable.
    report_dir = Path("eval-results")
    report_dir.mkdir(exist_ok=True)
    from datetime import datetime
    report_path = report_dir / f"{datetime.utcnow().strftime('%Y-%m-%d')}.json"
    report_path.write_text(json.dumps({
        "pass": results["pass"],
        "fail": results["fail"],
        "pass_rate": pass_rate,
        "failures": failures,
    }, indent=2))

    assert pass_rate >= 0.95, (
        f"Pass rate {pass_rate:.1%} below 95% threshold. "
        f"See {report_path} for failure details."
    )
