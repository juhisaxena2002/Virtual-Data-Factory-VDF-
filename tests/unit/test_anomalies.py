"""Tests for synthgen._anomalies.

Anomaly rates are statistical, so checks use a tolerance band. With
N=1000 trials at rate=0.1, the observed fraction should be in [0.07, 0.13]
with overwhelming probability (well within 3 sigma).
"""

from __future__ import annotations

import random

from synthgen._anomalies import apply_anomaly, apply_field_anomalies, new_drift_state
from synthgen.types import Anomaly, Field


def _baseline_field(name: str = "score") -> Field:
    return Field(name=name, type="float", provider="pyfloat")


class TestNullAnomaly:
    def test_replaces_value_with_none(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="null", rate=1.0)  # always fire
        rng = random.Random(0)
        ds = new_drift_state()
        assert apply_anomaly(42.0, anomaly, f, rng=rng, drift_state=ds) is None

    def test_never_fires_at_rate_zero(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="null", rate=0.0)
        rng = random.Random(0)
        ds = new_drift_state()
        for _ in range(100):
            assert apply_anomaly(42.0, anomaly, f, rng=rng, drift_state=ds) == 42.0

    def test_rate_within_tolerance(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="null", rate=0.1)
        rng = random.Random(42)
        ds = new_drift_state()
        nulls = sum(
            1 for _ in range(1000)
            if apply_anomaly(1.0, anomaly, f, rng=rng, drift_state=ds) is None
        )
        # Tolerance: 10% ± 3%.
        assert 70 <= nulls <= 130, f"Got {nulls} nulls out of 1000"


class TestStuckValue:
    def test_replaces_with_configured_value(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="stuck_value", rate=1.0, value=-1.0)
        rng = random.Random(0)
        ds = new_drift_state()
        assert apply_anomaly(99.0, anomaly, f, rng=rng, drift_state=ds) == -1.0


class TestInvalidFormat:
    def test_prefixes_invalid(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="invalid_format", rate=1.0)
        rng = random.Random(0)
        ds = new_drift_state()
        result = apply_anomaly("alice@example.com", anomaly, f, rng=rng, drift_state=ds)
        assert result == "INVALID_alice@example.com"


class TestSpike:
    def test_multiplies_numeric(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="spike", rate=1.0, magnitude=10.0)
        rng = random.Random(0)
        ds = new_drift_state()
        assert apply_anomaly(5.0, anomaly, f, rng=rng, drift_state=ds) == 50.0

    def test_passes_through_non_numeric(self) -> None:
        f = Field(name="name", type="string", provider="name")
        anomaly = Anomaly(type="spike", rate=1.0, magnitude=10.0)
        rng = random.Random(0)
        ds = new_drift_state()
        assert apply_anomaly("Alice", anomaly, f, rng=rng, drift_state=ds) == "Alice"


class TestOutlier:
    def test_modifies_numeric_value(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="outlier", rate=1.0, magnitude=3.0)
        rng = random.Random(0)
        ds = new_drift_state()
        result = apply_anomaly(10.0, anomaly, f, rng=rng, drift_state=ds)
        # Outlier adds gaussian noise — almost certainly differs from baseline.
        assert result != 10.0
        assert isinstance(result, float)


class TestDrift:
    def test_accumulates_across_rows(self) -> None:
        f = _baseline_field()
        anomaly = Anomaly(type="drift", rate=1.0, magnitude=0.5)
        rng = random.Random(0)
        ds = new_drift_state()
        # Apply the anomaly three times — drift should accumulate.
        v1 = apply_anomaly(0.0, anomaly, f, rng=rng, drift_state=ds)
        v2 = apply_anomaly(0.0, anomaly, f, rng=rng, drift_state=ds)
        v3 = apply_anomaly(0.0, anomaly, f, rng=rng, drift_state=ds)
        assert v1 == 0.5
        assert v2 == 1.0
        assert v3 == 1.5

    def test_independent_state_per_field(self) -> None:
        f1 = _baseline_field("score_a")
        f2 = _baseline_field("score_b")
        anomaly = Anomaly(type="drift", rate=1.0, magnitude=1.0)
        rng = random.Random(0)
        ds = new_drift_state()
        a1 = apply_anomaly(0.0, anomaly, f1, rng=rng, drift_state=ds)
        b1 = apply_anomaly(0.0, anomaly, f2, rng=rng, drift_state=ds)
        a2 = apply_anomaly(0.0, anomaly, f1, rng=rng, drift_state=ds)
        assert a1 == 1.0
        assert b1 == 1.0
        assert a2 == 2.0  # field a's drift, not affected by field b


class TestMultipleAnomalies:
    def test_apply_field_anomalies_chains_them(self) -> None:
        f = Field(
            name="score",
            type="float",
            provider="pyfloat",
            anomalies=(
                Anomaly(type="spike", rate=1.0, magnitude=10.0),
                # After spike: 50.0 -> spike makes it 500.0
                # Then drift adds another 1.0
                Anomaly(type="drift", rate=1.0, magnitude=1.0),
            ),
        )
        rng = random.Random(0)
        ds = new_drift_state()
        result = apply_field_anomalies(50.0, f, rng=rng, drift_state=ds)
        assert result == 501.0
