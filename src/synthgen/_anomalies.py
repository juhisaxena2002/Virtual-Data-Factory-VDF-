"""Anomaly injection.

Anomalies are applied in a *second pass* after baseline value generation.
This separation makes both phases independently testable and lets the
generator stay simple.

Each anomaly type is one pure function (or simple branch in
:func:`apply_anomaly`) that decides — based on its rate — whether to
modify the value for a given row.

State is held only for ``drift``, which needs a running offset across
rows. The state dict is keyed by field name and reset per generation run.
"""

from __future__ import annotations

import random
from typing import Any

from .types import Anomaly, Field

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
# ``drift`` is the one stateful anomaly. We track per-field cumulative offset
# so that successive rows drift further from the baseline.
DriftState = dict[str, float]


def new_drift_state() -> DriftState:
    """Return a fresh per-run drift state."""
    return {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def apply_anomaly(
    value: Any,
    anomaly: Anomaly,
    field: Field,
    *,
    rng: random.Random,
    drift_state: DriftState,
) -> Any:
    """Maybe modify ``value`` based on the anomaly's rate.

    Roll the dice. If we miss the rate, return the value unchanged.
    Otherwise dispatch on anomaly type.

    Parameters
    ----------
    value
        The baseline value produced by the generator for this row.
    anomaly
        The anomaly config from the spec.
    field
        The field this value belongs to (used for type-aware behavior).
    rng
        Random generator — passed in so the whole pipeline is seedable.
    drift_state
        Per-run dict tracking cumulative drift offsets.
    """
    if rng.random() >= anomaly.rate:
        return value

    t = anomaly.type
    mag = anomaly.magnitude

    if t == "null":
        return None

    if t == "stuck_value":
        return anomaly.value

    if t == "invalid_format":
        # Tag the value as invalid in a way that survives string conversion.
        return f"INVALID_{value}"

    if t == "spike":
        # Multiply numeric values; pass through non-numeric.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value * (mag or 10.0)
        return value

    if t == "outlier":
        # Add a few standard deviations of noise to numeric values.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            std_devs = mag or 3.0
            # Use the rng to make this deterministic given a seed.
            offset = rng.gauss(0.0, 1.0) * std_devs
            return value + offset
        return value

    if t == "duplicate":
        # The generator handles emitting the value twice; here we just
        # signal the intent by returning the value unchanged.
        # (Phase 2 may add explicit duplication in the generator loop.)
        return value

    if t == "drift":
        # Accumulate offset per field across rows.
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            step = mag or 0.1
            drift_state[field.name] = drift_state.get(field.name, 0.0) + step
            return value + drift_state[field.name]
        return value

    # Unknown type — shouldn't reach here because validation catches it,
    # but stay defensive.
    return value


def apply_field_anomalies(
    value: Any,
    field: Field,
    *,
    rng: random.Random,
    drift_state: DriftState,
) -> Any:
    """Apply every anomaly configured on a field, in order."""
    for anomaly in field.anomalies:
        value = apply_anomaly(value, anomaly, field, rng=rng, drift_state=drift_state)
    return value
