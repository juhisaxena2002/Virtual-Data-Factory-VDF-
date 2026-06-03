"""Tests for synthgen._generator."""

from __future__ import annotations

import pytest

from synthgen import GenerationError
from synthgen._generator import generate
from synthgen._schema import validate_spec
from synthgen.types import Field, Spec


class TestBasicGeneration:
    def test_produces_requested_row_count(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        records = generate(spec)
        assert len(records) == 10

    def test_each_record_has_all_fields(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        records = generate(spec)
        for r in records:
            assert set(r.keys()) == {"user_id", "email"}

    def test_email_field_produces_email_strings(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        records = generate(spec)
        for r in records:
            assert "@" in r["email"]


class TestDeterminism:
    def test_same_seed_produces_identical_output(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        a = generate(spec, seed=42)
        b = generate(spec, seed=42)
        assert a == b

    def test_different_seeds_produce_different_output(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        a = generate(spec, seed=42)
        b = generate(spec, seed=43)
        assert a != b

    def test_no_seed_produces_different_output(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        a = generate(spec)
        b = generate(spec)
        # Statistically all but certain to differ.
        assert a != b


class TestNumericDistributions:
    def test_normal_distribution_stays_in_range(self, numeric_spec_dict: dict) -> None:
        numeric_spec_dict["count"] = 200
        spec = validate_spec(numeric_spec_dict)
        records = generate(spec, seed=1)
        for r in records:
            assert 0 <= r["score"] <= 100

    def test_int_type_returns_ints(self) -> None:
        spec = Spec(
            dataset_name="ages",
            count=20,
            fields=(
                Field(
                    name="age",
                    type="int",
                    provider="pyint",
                    args={"min_value": 18, "max_value": 65},
                    distribution="normal",
                ),
            ),
        )
        records = generate(spec, seed=1)
        for r in records:
            assert isinstance(r["age"], int)
            assert 18 <= r["age"] <= 65


class TestProviders:
    @pytest.mark.parametrize("provider,expected_type", [
        ("name", str),
        ("email", str),
        ("uuid4", str),
        ("latitude", float),
        ("longitude", float),
        ("ipv4", str),
        ("company", str),
    ])
    def test_provider_returns_expected_type(self, provider: str, expected_type: type) -> None:
        spec = Spec(
            dataset_name="t",
            count=5,
            fields=(Field(name="v", type="string", provider=provider),),
        )
        records = generate(spec, seed=1)
        for r in records:
            assert isinstance(r["v"], expected_type)

    def test_random_element_picks_from_elements(self) -> None:
        spec = Spec(
            dataset_name="t",
            count=50,
            fields=(
                Field(
                    name="status",
                    type="string",
                    provider="random_element",
                    args={"elements": ["new", "active", "done"]},
                ),
            ),
        )
        records = generate(spec, seed=1)
        for r in records:
            assert r["status"] in {"new", "active", "done"}


class TestErrorPaths:
    def test_unknown_provider_in_spec_raises(self) -> None:
        # Bypass validation and feed the generator a bad spec directly.
        spec = Spec(
            dataset_name="t",
            count=1,
            fields=(Field(name="x", type="string", provider="ghost"),),
        )
        with pytest.raises(GenerationError, match="Unknown provider"):
            generate(spec)
