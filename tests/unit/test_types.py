"""Tests for synthgen.types — Spec, Field, Anomaly dataclasses."""

from __future__ import annotations

import pytest

from synthgen.types import Anomaly, Field, Spec


class TestSpec:
    def test_frozen(self) -> None:
        spec = Spec(dataset_name="x", fields=(), count=10)
        with pytest.raises(Exception):  # FrozenInstanceError
            spec.count = 20  # type: ignore[misc]

    def test_with_count_returns_new_instance(self) -> None:
        spec = Spec(dataset_name="x", fields=(), count=10)
        new = spec.with_count(50)
        assert spec.count == 10  # unchanged
        assert new.count == 50

    def test_round_trip(self, simple_spec_dict: dict) -> None:
        spec = Spec.from_dict(simple_spec_dict)
        out = spec.to_dict()
        # to_dict preserves the essentials.
        assert out["dataset_name"] == "users"
        assert len(out["fields"]) == 2

    def test_stream_interval_defaults_none(self) -> None:
        spec = Spec(dataset_name="x", fields=(), count=10)
        assert spec.stream_interval_sec is None
        # Omitted from to_dict when not set.
        assert "stream_interval_sec" not in spec.to_dict()

    def test_stream_interval_round_trip(self, simple_spec_dict: dict) -> None:
        raw = {**simple_spec_dict, "stream_interval_sec": 2.5}
        spec = Spec.from_dict(raw)
        assert spec.stream_interval_sec == 2.5
        assert spec.to_dict()["stream_interval_sec"] == 2.5

    def test_with_count_preserves_stream_interval(self) -> None:
        spec = Spec(dataset_name="x", fields=(), count=10, stream_interval_sec=3.0)
        assert spec.with_count(50).stream_interval_sec == 3.0


class TestField:
    def test_default_args(self) -> None:
        f = Field(name="x", type="string", provider="email")
        assert f.args == {}
        assert f.distribution is None
        assert f.anomalies == ()

    def test_with_anomalies(self) -> None:
        f = Field(
            name="x",
            type="float",
            provider="pyfloat",
            anomalies=(Anomaly(type="null", rate=0.1),),
        )
        assert len(f.anomalies) == 1
        assert f.anomalies[0].rate == 0.1

    def test_round_trip(self) -> None:
        original = Field(
            name="score",
            type="float",
            provider="pyfloat",
            args={"min_value": 0, "max_value": 100},
            distribution="normal",
            anomalies=(Anomaly(type="null", rate=0.05),),
        )
        round_tripped = Field.from_dict(original.to_dict())
        assert original == round_tripped


class TestAnomaly:
    def test_minimal(self) -> None:
        a = Anomaly(type="null", rate=0.1)
        assert a.magnitude is None
        assert a.value is None

    def test_to_dict_omits_optional_none_fields(self) -> None:
        a = Anomaly(type="null", rate=0.1)
        assert a.to_dict() == {"type": "null", "rate": 0.1}

    def test_round_trip(self) -> None:
        a = Anomaly(type="stuck_value", rate=0.5, value=-999)
        assert Anomaly.from_dict(a.to_dict()) == a
