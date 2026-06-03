"""Shared pytest fixtures.

Re-usable spec dicts and MockBackend instances for the unit tests.
"""

from __future__ import annotations

import pytest

from synthgen import Client
from synthgen.backends import MockBackend


# ---------------------------------------------------------------------------
# Canned specs — used across multiple tests
# ---------------------------------------------------------------------------
@pytest.fixture
def simple_spec_dict() -> dict:
    """A minimal valid spec dict."""
    return {
        "dataset_name": "users",
        "count": 10,
        "fields": [
            {"name": "user_id", "type": "uuid", "provider": "uuid4"},
            {"name": "email", "type": "string", "provider": "email"},
        ],
    }


@pytest.fixture
def numeric_spec_dict() -> dict:
    """A spec exercising numeric distributions."""
    return {
        "dataset_name": "scores",
        "count": 20,
        "fields": [
            {"name": "user_id", "type": "uuid", "provider": "uuid4"},
            {
                "name": "score",
                "type": "float",
                "provider": "pyfloat",
                "args": {"min_value": 0, "max_value": 100, "right_digits": 2},
                "distribution": "normal",
            },
        ],
    }


@pytest.fixture
def anomaly_spec_dict() -> dict:
    """A spec with anomalies on a numeric field."""
    return {
        "dataset_name": "sensor_readings",
        "count": 100,
        "fields": [
            {
                "name": "temperature_c",
                "type": "float",
                "provider": "pyfloat",
                "args": {"min_value": 20, "max_value": 30, "right_digits": 2},
                "distribution": "normal",
                "anomalies": [
                    {"type": "null", "rate": 0.1},
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_client(simple_spec_dict: dict) -> Client:
    """A Client backed by MockBackend, returning ``simple_spec_dict`` for any prompt.

    ``cache=None`` keeps unit tests fast and offline — the default cache
    would otherwise try to load MiniLM and touch the user cache dir.
    """
    backend = MockBackend(default=simple_spec_dict)
    return Client(backend=backend, cache=None)
