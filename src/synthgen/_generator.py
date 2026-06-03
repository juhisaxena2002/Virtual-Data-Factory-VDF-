"""Record generation.

Pure function: ``generate(spec, seed) -> list[Record]``. No I/O, no LLM
call, no network. This is what makes the SDK testable.

Architecture:

* A **provider dispatch table** maps provider names (e.g. ``"email"``,
  ``"pyfloat"``) to callables that produce a single value given keyword
  arguments.
* For numeric fields with a ``distribution``, the provider's
  ``min_value``/``max_value`` args define the support, and the chosen
  distribution shapes the sampling.
* Anomalies are applied in a second pass via :mod:`._anomalies`.
"""

from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np
from faker import Faker

from ._anomalies import apply_field_anomalies, new_drift_state
from .errors import GenerationError
from .types import (
    DerivedCorrelation,
    Field,
    MultivariateCorrelation,
    Record,
    Spec,
)

# A provider callable takes its keyword args and produces a value.
Provider = Callable[..., Any]


# ---------------------------------------------------------------------------
# Dispatch table builder
# ---------------------------------------------------------------------------
def _build_dispatch(faker: Faker, rng: np.random.Generator) -> dict[str, Provider]:
    """Build the provider dispatch table for one generation run.

    Closes over the seeded ``faker`` and numpy ``rng`` so providers stay
    deterministic when a seed is set.
    """
    # NOTE: every callable here must accept arbitrary kwargs because the
    # spec may pass through args the provider doesn't recognise. Faker
    # generally tolerates extra kwargs; for our own wrappers we ignore them.
    return {
        # ---- Person ----
        "name":         lambda **kw: faker.name(),
        "first_name":   lambda **kw: faker.first_name(),
        "last_name":    lambda **kw: faker.last_name(),
        "email":        lambda **kw: faker.email(),
        "phone_number": lambda **kw: faker.phone_number(),
        "job":          lambda **kw: faker.job(),
        # ---- Location ----
        "address":      lambda **kw: faker.address(),
        "city":         lambda **kw: faker.city(),
        "country":      lambda **kw: faker.country(),
        "country_code": lambda **kw: faker.country_code(),
        "latitude":     lambda **kw: float(faker.latitude()),
        "longitude":    lambda **kw: float(faker.longitude()),
        # ---- Internet ----
        "ipv4":         lambda **kw: faker.ipv4(),
        "url":          lambda **kw: faker.url(),
        "user_agent":   lambda **kw: faker.user_agent(),
        "user_name":    lambda **kw: faker.user_name(),
        # ---- Business ----
        "company":             lambda **kw: faker.company(),
        "currency_code":       lambda **kw: faker.currency_code(),
        "credit_card_number":  lambda **kw: faker.credit_card_number(),
        # ---- Identifiers ----
        "uuid4":        lambda **kw: str(faker.uuid4()),
        # ---- Date/time ----
        "date_time_between": lambda **kw: faker.date_time_between(**kw).isoformat(),
        "date_between":      lambda **kw: faker.date_between(**kw).isoformat(),
        "time":              lambda **kw: faker.time(),
        # ---- Numerics ----
        # pyfloat/pyint are special: distribution may override their default sampling.
        # The base implementation is here; distribution handling happens in _gen_field.
        "pyfloat":      lambda **kw: faker.pyfloat(**kw),
        "pyint":        lambda **kw: faker.pyint(**kw),
        # ---- Choice ----
        "random_element": lambda elements=("a", "b", "c"), **kw: faker.random_element(elements),
        # ---- Text ----
        "sentence":     lambda **kw: faker.sentence(**kw),
        "word":         lambda **kw: faker.word(**kw),
        "text":         lambda **kw: faker.text(**kw),
        "bothify":      lambda text="###-???", **kw: faker.bothify(text=text),
    }


# ---------------------------------------------------------------------------
# Distribution-aware numeric sampling
# ---------------------------------------------------------------------------
def _sample_numeric(
    field: Field,
    rng: np.random.Generator,
    dispatch: dict[str, Provider],
) -> float | int:
    """Sample a numeric value, honoring the field's distribution if set."""
    args = field.args
    lo = float(args.get("min_value", 0))
    hi = float(args.get("max_value", 100))

    dist = field.distribution
    if dist == "normal":
        # Center on midpoint; std-dev = 1/6 of range so ~99.7% in [lo, hi].
        mid = (lo + hi) / 2
        std = (hi - lo) / 6
        v = float(rng.normal(mid, std))
        # Clip so we don't blow past the requested range.
        v = max(lo, min(hi, v))
    elif dist == "exponential":
        # Exponential in [0, hi-lo], shifted to [lo, hi].
        scale = (hi - lo) / 4 or 1.0
        v = lo + float(rng.exponential(scale))
        v = min(hi, v)
    elif dist == "uniform" or dist is None:
        v = float(rng.uniform(lo, hi))
    else:
        # "choice" / "sequential" don't apply to plain numerics; fall back.
        return dispatch[field.provider](**field.args)

    # Match the field type.
    if field.type == "int":
        return int(round(v))
    if "right_digits" in args:
        return round(v, int(args["right_digits"]))
    return v


# ---------------------------------------------------------------------------
# Per-field value generation
# ---------------------------------------------------------------------------
def _gen_field(field: Field, dispatch: dict[str, Provider], rng: np.random.Generator) -> Any:
    """Produce one baseline value for the given field."""
    # Distribution-aware numeric path.
    if field.provider in {"pyfloat", "pyint"} and field.distribution:
        return _sample_numeric(field, rng, dispatch)

    provider = dispatch.get(field.provider)
    if provider is None:
        # Should never happen — validation guarantees provider is in dispatch.
        raise GenerationError(
            f"Unknown provider {field.provider!r} for field {field.name!r}. "
            f"This is a bug — validation should have rejected it earlier."
        )

    try:
        return provider(**field.args)
    except TypeError as e:
        raise GenerationError(
            f"Provider {field.provider!r} for field {field.name!r} rejected its args: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Correlation appliers — run after independent generation, before anomalies
# ---------------------------------------------------------------------------
def _cast_to_field_type(value: float, field: Field | None) -> Any:
    """Match the field's declared type / precision (int rounding, decimals)."""
    if field is None:
        return value
    if field.type == "int":
        return int(round(value))
    if "right_digits" in field.args:
        return round(value, int(field.args["right_digits"]))
    return value


def _apply_derived(
    entry: DerivedCorrelation,
    row: Record,
    fields_by_name: dict[str, Field],
    rng: np.random.Generator,
) -> None:
    """Overwrite ``row[target]`` with ``slope*source + intercept + noise``."""
    src_val = row.get(entry.source)
    if not isinstance(src_val, (int, float)) or isinstance(src_val, bool):
        return  # nothing numeric to derive from (e.g. anomaly NULLed it)
    noise = float(rng.normal(0.0, entry.noise_std)) if entry.noise_std > 0 else 0.0
    v = entry.slope * float(src_val) + entry.intercept + noise
    if entry.min_value is not None:
        v = max(entry.min_value, v)
    if entry.max_value is not None:
        v = min(entry.max_value, v)
    row[entry.target] = _cast_to_field_type(v, fields_by_name.get(entry.target))


def _apply_multivariate(
    entry: MultivariateCorrelation,
    cholesky: np.ndarray,
    row: Record,
    fields_by_name: dict[str, Field],
    rng: np.random.Generator,
) -> None:
    """Replace the listed fields with a joint multivariate-normal sample.

    Per-field marginals come from ``min_value`` / ``max_value`` using the
    same normal-distribution convention as :func:`_sample_numeric`
    (mid-point mean, ±3σ over the full range).
    """
    z = rng.standard_normal(len(entry.fields))
    x = cholesky @ z  # correlated standard normals
    for i, name in enumerate(entry.fields):
        field = fields_by_name.get(name)
        if field is None:
            continue
        lo = float(field.args.get("min_value", 0))
        hi = float(field.args.get("max_value", 100))
        mu = (lo + hi) / 2.0
        sigma = (hi - lo) / 6.0 if hi > lo else 1.0
        v = mu + sigma * float(x[i])
        v = max(lo, min(hi, v))
        row[name] = _cast_to_field_type(v, field)


def _precompute_correlations(
    spec: Spec,
) -> list[tuple[str, Any, np.ndarray | None]]:
    """Pre-build the Cholesky factor for each multivariate entry once."""
    out: list[tuple[str, Any, np.ndarray | None]] = []
    for entry in spec.correlations:
        if isinstance(entry, MultivariateCorrelation):
            R = np.array(entry.correlation, dtype=float)
            try:
                L = np.linalg.cholesky(R)
            except np.linalg.LinAlgError:
                # Validator should have repaired non-PSD inputs; if a
                # corner case slipped through, fall back to identity so
                # the run produces independent draws instead of crashing.
                L = np.eye(len(entry.fields))
            out.append(("multivariate", entry, L))
        else:
            out.append(("derived", entry, None))
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate(spec: Spec, seed: int | None = None) -> list[Record]:
    """Generate ``spec.count`` records from the given spec.

    Parameters
    ----------
    spec
        Validated spec (use ``Client.compile_spec`` or
        ``validate_spec`` to produce one).
    seed
        Optional RNG seed. When set, generation is deterministic — the
        same spec + seed produces byte-identical output.
    """
    if seed is not None:
        # Faker uses its own RNG; we have to seed each independently.
        faker = Faker()
        Faker.seed(seed)
        random.seed(seed)
        np_rng = np.random.default_rng(seed)
        py_rng = random.Random(seed)
    else:
        faker = Faker()
        np_rng = np.random.default_rng()
        py_rng = random.Random()

    dispatch = _build_dispatch(faker, np_rng)
    drift_state = new_drift_state()
    fields_by_name = {f.name: f for f in spec.fields}
    correlation_plan = _precompute_correlations(spec)

    records: list[Record] = []
    for _ in range(spec.count):
        row: Record = {}
        # Pass 1: independent value for every field.
        for field in spec.fields:
            row[field.name] = _gen_field(field, dispatch, np_rng)
        # Pass 2: apply correlations — overwrites values for involved fields.
        # Order: spec order. A target field set by an earlier entry can be
        # read as a source by a later derived entry.
        for kind, entry, cholesky in correlation_plan:
            if kind == "derived":
                _apply_derived(entry, row, fields_by_name, np_rng)
            else:
                _apply_multivariate(entry, cholesky, row, fields_by_name, np_rng)
        # Pass 3: anomalies (per-field, preserving drift state across rows).
        for field in spec.fields:
            if field.anomalies:
                row[field.name] = apply_field_anomalies(
                    row[field.name], field, rng=py_rng, drift_state=drift_state,
                )
        records.append(row)

    return records
