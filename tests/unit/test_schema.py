"""Tests for synthgen._schema."""

from __future__ import annotations

import pytest

from synthgen import SpecValidationError
from synthgen._schema import ALLOWED_PROVIDERS, validate_spec
from synthgen.types import Spec


class TestHappyPath:
    def test_validates_minimal_spec(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        assert isinstance(spec, Spec)
        assert spec.dataset_name == "users"
        assert spec.count == 10
        assert len(spec.fields) == 2

    def test_round_trip_via_dict(self, simple_spec_dict: dict) -> None:
        spec = validate_spec(simple_spec_dict)
        round_tripped = validate_spec(spec.to_dict())
        assert spec == round_tripped


class TestRowCap:
    def test_clamps_count_above_cap(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["count"] = 199
        spec = validate_spec(simple_spec_dict, max_row_cap=50)
        assert spec.count == 50

    def test_schema_rejects_count_above_200(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["count"] = 201
        with pytest.raises(SpecValidationError, match="maximum"):
            validate_spec(simple_spec_dict)

    def test_schema_rejects_zero_count(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["count"] = 0
        with pytest.raises(SpecValidationError):
            validate_spec(simple_spec_dict)


class TestRequiredFields:
    def test_missing_dataset_name(self, simple_spec_dict: dict) -> None:
        del simple_spec_dict["dataset_name"]
        with pytest.raises(SpecValidationError, match="dataset_name"):
            validate_spec(simple_spec_dict)

    def test_missing_fields(self, simple_spec_dict: dict) -> None:
        del simple_spec_dict["fields"]
        with pytest.raises(SpecValidationError, match="fields"):
            validate_spec(simple_spec_dict)

    def test_field_missing_provider(self, simple_spec_dict: dict) -> None:
        del simple_spec_dict["fields"][0]["provider"]
        with pytest.raises(SpecValidationError, match="provider"):
            validate_spec(simple_spec_dict)

    def test_empty_fields_rejected(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"] = []
        with pytest.raises(SpecValidationError):
            validate_spec(simple_spec_dict)


class TestAllowList:
    def test_unknown_provider_rejected(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"][0]["provider"] = "not_a_real_provider"
        with pytest.raises(SpecValidationError, match="allow-list"):
            validate_spec(simple_spec_dict)

    def test_all_listed_providers_are_strings(self) -> None:
        # Sanity check the allow-list itself.
        assert all(isinstance(p, str) for p in ALLOWED_PROVIDERS)
        assert "email" in ALLOWED_PROVIDERS
        assert "uuid4" in ALLOWED_PROVIDERS


class TestFieldNames:
    def test_field_name_must_be_snake_case(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"][0]["name"] = "BadCamelCase"
        with pytest.raises(SpecValidationError):
            validate_spec(simple_spec_dict)

    def test_field_name_cannot_start_with_digit(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"][0]["name"] = "1field"
        with pytest.raises(SpecValidationError):
            validate_spec(simple_spec_dict)


class TestAnomalies:
    def test_valid_anomaly_passes(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"][0]["anomalies"] = [
            {"type": "null", "rate": 0.1},
        ]
        spec = validate_spec(simple_spec_dict)
        assert len(spec.fields[0].anomalies) == 1

    def test_invalid_anomaly_type_rejected(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"][0]["anomalies"] = [
            {"type": "not_a_real_anomaly", "rate": 0.1},
        ]
        with pytest.raises(SpecValidationError):
            validate_spec(simple_spec_dict)

    def test_anomaly_rate_out_of_range(self, simple_spec_dict: dict) -> None:
        simple_spec_dict["fields"][0]["anomalies"] = [
            {"type": "null", "rate": 1.5},
        ]
        with pytest.raises(SpecValidationError):
            validate_spec(simple_spec_dict)
