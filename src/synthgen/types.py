"""Public type definitions for synthgen.

These are the dataclasses users interact with. All are frozen — immutable,
hashable, comparable. Mutations return new instances via :meth:`Spec.with_count`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Type aliases — give the JSON Schema a Python-level vocabulary
# ---------------------------------------------------------------------------
AnomalyType = Literal[
    "null",
    "outlier",
    "stuck_value",
    "spike",
    "duplicate",
    "drift",
    "invalid_format",
]

Distribution = Literal["uniform", "normal", "exponential", "choice", "sequential"]

FieldType = Literal["string", "int", "float", "bool", "datetime", "uuid"]

# A generated row is an open dict — keys are field names, values vary by type.
Record = dict[str, Any]


# ---------------------------------------------------------------------------
# Anomaly
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Anomaly:
    """Anomaly injection directive for a single field.

    Parameters
    ----------
    type
        Kind of anomaly to inject (see ``AnomalyType``).
    rate
        Fraction of rows to affect, 0.0–1.0.
    magnitude
        Scaling factor — meaning depends on the anomaly type
        (e.g. number of std-devs for ``outlier``, multiplier for ``spike``).
    value
        For ``stuck_value`` — the value to inject.
    """

    type: AnomalyType
    rate: float
    magnitude: float | None = None
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "rate": self.rate}
        if self.magnitude is not None:
            out["magnitude"] = self.magnitude
        if self.value is not None:
            out["value"] = self.value
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Anomaly:
        return cls(
            type=raw["type"],
            rate=float(raw["rate"]),
            magnitude=raw.get("magnitude"),
            value=raw.get("value"),
        )


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Field:
    """One column in the generated dataset.

    A field has a ``name``, a ``type`` (used for serialization decisions),
    and a ``provider`` (which Faker/Mimesis function produces values).
    Optional ``distribution`` controls how numeric values are sampled.
    Optional ``anomalies`` inject noise.
    """

    name: str
    type: FieldType
    provider: str
    args: dict[str, Any] = field(default_factory=dict)
    distribution: Distribution | None = None
    anomalies: tuple[Anomaly, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "provider": self.provider,
        }
        if self.args:
            out["args"] = dict(self.args)
        if self.distribution is not None:
            out["distribution"] = self.distribution
        if self.anomalies:
            out["anomalies"] = [a.to_dict() for a in self.anomalies]
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Field:
        return cls(
            name=raw["name"],
            type=raw["type"],
            provider=raw["provider"],
            args=dict(raw.get("args", {})),
            distribution=raw.get("distribution"),
            anomalies=tuple(Anomaly.from_dict(a) for a in raw.get("anomalies", [])),
        )


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------
# Two flavors that the LLM picks based on the prompt:
#
#   * ``derived``      — a target field is a linear function of one source
#                        field plus optional Gaussian noise. Cheap, intuitive,
#                        easy for the LLM to emit.
#   * ``multivariate`` — a group of fields is drawn jointly from a
#                        multivariate normal whose pairwise correlations
#                        follow a user-supplied matrix. Captures every
#                        pairwise relationship at once but requires a valid
#                        (positive semi-definite) correlation matrix.
#
# Absence of a correlation entry means independent sampling — the historical
# behavior. Validation in :mod:`._schema` enforces field references, numeric
# types, matrix shape and PSD repair.
CorrelationMode = Literal["derived", "multivariate"]


@dataclass(frozen=True)
class DerivedCorrelation:
    """A target field expressed as ``slope * source + intercept + N(0, noise_std)``.

    Optional ``min_value`` / ``max_value`` clip the result so it can stay
    inside the target field's natural range (e.g. humidity in [0, 100]).
    """

    source: str
    target: str
    slope: float
    intercept: float = 0.0
    noise_std: float = 0.0
    min_value: float | None = None
    max_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "mode": "derived",
            "source": self.source,
            "target": self.target,
            "slope": self.slope,
            "intercept": self.intercept,
            "noise_std": self.noise_std,
        }
        if self.min_value is not None:
            out["min_value"] = self.min_value
        if self.max_value is not None:
            out["max_value"] = self.max_value
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> DerivedCorrelation:
        return cls(
            source=raw["source"],
            target=raw["target"],
            slope=float(raw["slope"]),
            intercept=float(raw.get("intercept", 0.0)),
            noise_std=float(raw.get("noise_std", 0.0)),
            min_value=float(raw["min_value"]) if raw.get("min_value") is not None else None,
            max_value=float(raw["max_value"]) if raw.get("max_value") is not None else None,
        )


@dataclass(frozen=True)
class MultivariateCorrelation:
    """A group of numeric fields drawn jointly from N(mu, Sigma).

    The ``correlation`` matrix is N×N, symmetric, with 1.0 on the
    diagonal. Each field's marginal mean/std is derived from its own
    ``min_value`` / ``max_value`` and the normal distribution convention
    used in :func:`_generator._sample_numeric`.
    """

    fields: tuple[str, ...]
    correlation: tuple[tuple[float, ...], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "multivariate",
            "fields": list(self.fields),
            "correlation": [list(row) for row in self.correlation],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MultivariateCorrelation:
        return cls(
            fields=tuple(raw["fields"]),
            correlation=tuple(
                tuple(float(x) for x in row) for row in raw["correlation"]
            ),
        )


Correlation = DerivedCorrelation | MultivariateCorrelation


def _correlation_from_dict(raw: dict[str, Any]) -> Correlation:
    mode = raw.get("mode")
    if mode == "derived":
        return DerivedCorrelation.from_dict(raw)
    if mode == "multivariate":
        return MultivariateCorrelation.from_dict(raw)
    raise ValueError(f"Unknown correlation mode: {mode!r}")


@dataclass(frozen=True)
class Spec:
    """A complete data specification — what the generator consumes.

    Returned by ``Client.compile_spec(prompt)``. Frozen — use
    :meth:`with_count` to produce a modified copy.

    ``stream_interval_sec`` is optional streaming metadata: when the
    source prompt mentions a cadence ("one reading every 2 seconds"),
    the LLM records it here. ``None`` means the prompt said nothing
    about streaming rate.
    """

    dataset_name: str
    fields: tuple[Field, ...]
    count: int = 100
    stream_interval_sec: float | None = None
    correlations: tuple[Correlation, ...] = ()

    def with_count(self, count: int) -> Spec:
        """Return a new ``Spec`` with the given count."""
        return replace(self, count=count)

    def with_correlations(self, correlations: tuple[Correlation, ...]) -> Spec:
        """Return a copy with ``correlations`` replaced.

        Used by the CLI ``--correlation`` filter to force a single mode
        (e.g. drop multivariate entries and keep only derived).
        """
        return replace(self, correlations=correlations)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "dataset_name": self.dataset_name,
            "count": self.count,
            "fields": [f.to_dict() for f in self.fields],
        }
        if self.stream_interval_sec is not None:
            out["stream_interval_sec"] = self.stream_interval_sec
        if self.correlations:
            out["correlations"] = [c.to_dict() for c in self.correlations]
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Spec:
        interval = raw.get("stream_interval_sec")
        return cls(
            dataset_name=raw["dataset_name"],
            count=int(raw.get("count", 100)),
            fields=tuple(Field.from_dict(f) for f in raw["fields"]),
            stream_interval_sec=float(interval) if interval is not None else None,
            correlations=tuple(
                _correlation_from_dict(c) for c in raw.get("correlations", [])
            ),
        )
