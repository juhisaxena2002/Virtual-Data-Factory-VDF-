"""Tests for inter-field correlations: derived, multivariate, and mode filter."""

from __future__ import annotations

import math

import numpy as np
import pytest

from synthgen import (
    Client,
    DerivedCorrelation,
    MultivariateCorrelation,
    SpecValidationError,
)
from synthgen._generator import generate
from synthgen._schema import validate_spec
from synthgen.backends import MockBackend
from synthgen.types import Spec


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------
def _two_numeric_spec(correlations: list[dict] | None = None) -> dict:
    return {
        "dataset_name": "sensors",
        "count": 200,
        "fields": [
            {
                "name": "temperature_c",
                "type": "float",
                "provider": "pyfloat",
                "args": {"min_value": 18, "max_value": 30, "right_digits": 2},
                "distribution": "normal",
            },
            {
                "name": "humidity_pct",
                "type": "float",
                "provider": "pyfloat",
                "args": {"min_value": 10, "max_value": 100, "right_digits": 2},
                "distribution": "normal",
            },
        ],
        **({"correlations": correlations} if correlations is not None else {}),
    }


def _three_numeric_spec(correlations: list[dict] | None = None) -> dict:
    return {
        "dataset_name": "factory",
        "count": 200,
        "fields": [
            {"name": "a", "type": "float", "provider": "pyfloat",
             "args": {"min_value": 0, "max_value": 100}, "distribution": "normal"},
            {"name": "b", "type": "float", "provider": "pyfloat",
             "args": {"min_value": 0, "max_value": 100}, "distribution": "normal"},
            {"name": "c", "type": "float", "provider": "pyfloat",
             "args": {"min_value": 0, "max_value": 100}, "distribution": "normal"},
        ],
        **({"correlations": correlations} if correlations is not None else {}),
    }


# ---------------------------------------------------------------------------
# Derived correlation
# ---------------------------------------------------------------------------
class TestDerived:
    def test_target_equals_linear_function_of_source(self) -> None:
        # Zero noise → target is exactly slope*source + intercept (clipped).
        spec = validate_spec(_two_numeric_spec([{
            "mode": "derived",
            "source": "temperature_c",
            "target": "humidity_pct",
            "slope": -2.0,
            "intercept": 100.0,
            "noise_std": 0.0,
        }]))
        rows = generate(spec, seed=42)
        for row in rows:
            expected = -2.0 * row["temperature_c"] + 100.0
            assert math.isclose(row["humidity_pct"], expected, abs_tol=0.01)

    def test_negative_correlation_in_data(self) -> None:
        spec = validate_spec(_two_numeric_spec([{
            "mode": "derived",
            "source": "temperature_c",
            "target": "humidity_pct",
            "slope": -1.5,
            "intercept": 80.0,
            "noise_std": 1.0,
        }]))
        rows = generate(spec, seed=42)
        temps = np.array([r["temperature_c"] for r in rows])
        hums = np.array([r["humidity_pct"] for r in rows])
        corr = np.corrcoef(temps, hums)[0, 1]
        # Slope is negative; expect strongly negative correlation.
        assert corr < -0.85

    def test_clip_bounds_respected(self) -> None:
        spec = validate_spec(_two_numeric_spec([{
            "mode": "derived",
            "source": "temperature_c",
            "target": "humidity_pct",
            "slope": -10.0,        # huge slope -> would overflow without clip
            "intercept": 0.0,
            "noise_std": 0.0,
            "min_value": 10,
            "max_value": 95,
        }]))
        rows = generate(spec, seed=42)
        for r in rows:
            assert 10 <= r["humidity_pct"] <= 95


# ---------------------------------------------------------------------------
# Multivariate correlation
# ---------------------------------------------------------------------------
class TestMultivariate:
    def test_empirical_correlation_matches_target(self) -> None:
        target_R = [
            [1.0, 0.8, -0.3],
            [0.8, 1.0, -0.1],
            [-0.3, -0.1, 1.0],
        ]
        spec = validate_spec(_three_numeric_spec([{
            "mode": "multivariate",
            "fields": ["a", "b", "c"],
            "correlation": target_R,
        }]))
        rows = generate(spec, seed=42)
        arr = np.array([[r["a"], r["b"], r["c"]] for r in rows])
        empirical = np.corrcoef(arr, rowvar=False)
        # 200 samples → tolerance ~0.15 for each off-diagonal.
        for i in range(3):
            for j in range(3):
                assert abs(empirical[i, j] - target_R[i][j]) < 0.15

    def test_non_psd_matrix_is_repaired(self) -> None:
        # corr(a,b)=0.9, corr(b,c)=0.9, corr(a,c)=-0.9 is geometrically
        # impossible (smallest eigenvalue is very negative). The validator
        # should repair to nearest PSD with a warning, not raise.
        spec_dict = _three_numeric_spec([{
            "mode": "multivariate",
            "fields": ["a", "b", "c"],
            "correlation": [
                [1.0, 0.9, -0.9],
                [0.9, 1.0, 0.9],
                [-0.9, 0.9, 1.0],
            ],
        }])
        with pytest.warns(UserWarning, match="positive semi-definite"):
            spec = validate_spec(spec_dict)
        # Should still produce records.
        rows = generate(spec, seed=42)
        assert len(rows) == 200


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class TestCorrelationValidation:
    def test_derived_unknown_source_rejected(self) -> None:
        with pytest.raises(SpecValidationError, match="source"):
            validate_spec(_two_numeric_spec([{
                "mode": "derived", "source": "nope", "target": "humidity_pct",
                "slope": 1.0,
            }]))

    def test_derived_non_numeric_source_rejected(self) -> None:
        bad = _two_numeric_spec([{
            "mode": "derived", "source": "tag", "target": "humidity_pct",
            "slope": 1.0,
        }])
        bad["fields"].append({"name": "tag", "type": "string", "provider": "email"})
        with pytest.raises(SpecValidationError, match="numeric"):
            validate_spec(bad)

    def test_multivariate_wrong_matrix_size_rejected(self) -> None:
        with pytest.raises(SpecValidationError, match="2x2|matrix"):
            validate_spec(_two_numeric_spec([{
                "mode": "multivariate",
                "fields": ["temperature_c", "humidity_pct"],
                "correlation": [[1.0, 0.5, 0.0], [0.5, 1.0, 0.0]],
            }]))


# ---------------------------------------------------------------------------
# Client-level mode filter
# ---------------------------------------------------------------------------
class TestCorrelationModeFilter:
    def _backend_returning(self, spec_dict: dict) -> MockBackend:
        return MockBackend(default=spec_dict)

    def test_auto_keeps_what_llm_emitted(self) -> None:
        spec_dict = _two_numeric_spec([{
            "mode": "derived",
            "source": "temperature_c", "target": "humidity_pct",
            "slope": -1.0, "intercept": 50,
        }])
        client = Client(backend=self._backend_returning(spec_dict), cache=None)
        spec = client.compile_spec("p", correlation_mode="auto")
        assert len(spec.correlations) == 1
        assert isinstance(spec.correlations[0], DerivedCorrelation)

    def test_independent_strips_all_correlations(self) -> None:
        spec_dict = _two_numeric_spec([{
            "mode": "derived",
            "source": "temperature_c", "target": "humidity_pct",
            "slope": -1.0, "intercept": 50,
        }])
        client = Client(backend=self._backend_returning(spec_dict), cache=None)
        spec = client.compile_spec("p", correlation_mode="independent")
        assert spec.correlations == ()

    def test_derived_filter_drops_multivariate(self) -> None:
        spec_dict = _three_numeric_spec([
            {"mode": "derived", "source": "a", "target": "b",
             "slope": 1.0, "intercept": 0},
            {"mode": "multivariate", "fields": ["a", "c"],
             "correlation": [[1.0, 0.5], [0.5, 1.0]]},
        ])
        client = Client(backend=self._backend_returning(spec_dict), cache=None)
        spec = client.compile_spec("p", correlation_mode="derived")
        assert len(spec.correlations) == 1
        assert isinstance(spec.correlations[0], DerivedCorrelation)

    def test_multivariate_filter_drops_derived(self) -> None:
        spec_dict = _three_numeric_spec([
            {"mode": "derived", "source": "a", "target": "b",
             "slope": 1.0, "intercept": 0},
            {"mode": "multivariate", "fields": ["a", "c"],
             "correlation": [[1.0, 0.5], [0.5, 1.0]]},
        ])
        client = Client(backend=self._backend_returning(spec_dict), cache=None)
        spec = client.compile_spec("p", correlation_mode="multivariate")
        assert len(spec.correlations) == 1
        assert isinstance(spec.correlations[0], MultivariateCorrelation)

    def test_unknown_mode_raises(self) -> None:
        client = Client(backend=self._backend_returning(_two_numeric_spec()), cache=None)
        with pytest.raises(ValueError, match="Unknown correlation mode"):
            client.compile_spec("p", correlation_mode="nonsense")


# ---------------------------------------------------------------------------
# Round-trip: independent baseline
# ---------------------------------------------------------------------------
class TestIndependentBaseline:
    def test_no_correlation_yields_near_zero_pearson(self) -> None:
        spec = validate_spec(_two_numeric_spec())
        assert spec.correlations == ()
        rows = generate(spec, seed=42)
        temps = np.array([r["temperature_c"] for r in rows])
        hums = np.array([r["humidity_pct"] for r in rows])
        corr = np.corrcoef(temps, hums)[0, 1]
        # Sampled independently — at n=200, |corr| < 0.2 is a comfortable bound.
        assert abs(corr) < 0.2


# Keep type-checkers happy when Spec is unused locally.
_ = Spec
