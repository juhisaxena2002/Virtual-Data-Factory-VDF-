"""Spec validation.

Two layers of defense between the LLM and the generator:

1. JSON Schema validation — structural checks (required fields, types,
   ranges, enums).
2. Allow-list check — providers must be in :data:`ALLOWED_PROVIDERS`.

After validation, :func:`validate_spec` clamps ``count`` to ``max_row_cap``
defensively (the schema also caps it, but the LLM may suggest more if its
output is fed in by a different code path).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from .errors import SpecValidationError
from .types import Spec

# Numeric provider names — used to validate that fields referenced by
# correlations are quantitative. Kept inline (rather than imported from
# the generator dispatch) so validation doesn't depend on the generator.
_NUMERIC_PROVIDERS: frozenset[str] = frozenset({"pyfloat", "pyint"})

# ---------------------------------------------------------------------------
# Load the JSON Schema once at import time
# ---------------------------------------------------------------------------
_SCHEMA_PATH = Path(__file__).parent / "prompts" / "schema.json"
_SCHEMA: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = jsonschema.Draft202012Validator(_SCHEMA)


# ---------------------------------------------------------------------------
# Closed allow-list of providers
# ---------------------------------------------------------------------------
# Anything the LLM suggests that isn't on this list is rejected. Keeping the
# vocabulary closed means the generator never sees an unknown provider name.
ALLOWED_PROVIDERS: frozenset[str] = frozenset(
    {
        # Person
        "name",
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "job",
        # Location
        "address",
        "city",
        "country",
        "country_code",
        "latitude",
        "longitude",
        # Internet
        "ipv4",
        "url",
        "user_agent",
        "user_name",
        # Business
        "company",
        "currency_code",
        "credit_card_number",
        # Identifiers
        "uuid4",
        # Date/time
        "date_time_between",
        "date_between",
        "time",
        # Numerics
        "pyfloat",
        "pyint",
        # Choice
        "random_element",
        # Text
        "sentence",
        "word",
        "text",
        "bothify",
    }
)


def validate_spec(raw: dict[str, Any], max_row_cap: int = 200) -> Spec:
    """Validate a raw spec dict against the JSON Schema and the allow-list.

    Returns a typed :class:`Spec` on success. Raises
    :class:`SpecValidationError` on any structural problem.
    """
    # 1. Structural validation via JSON Schema.
    errors = sorted(_VALIDATOR.iter_errors(raw), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.absolute_path) or "<root>"
        raise SpecValidationError(
            f"Spec failed JSON Schema validation at {path}: {first.message}",
            errors=[
                {"path": ".".join(str(p) for p in e.absolute_path), "message": e.message}
                for e in errors
            ],
        )

    # 2. Provider allow-list.
    for f in raw["fields"]:
        provider = f["provider"]
        if provider not in ALLOWED_PROVIDERS:
            raise SpecValidationError(
                f"Provider {provider!r} is not in the allow-list. "
                f"Allowed providers: {sorted(ALLOWED_PROVIDERS)}",
            )

    # 3. Validate (and PSD-repair) correlations.
    raw = dict(raw)
    if raw.get("correlations"):
        raw["correlations"] = _validate_correlations(raw["correlations"], raw["fields"])

    # 4. Clamp count defensively.
    raw["count"] = min(int(raw.get("count", 100)), max_row_cap)

    return Spec.from_dict(raw)


# ---------------------------------------------------------------------------
# Correlation validation helpers
# ---------------------------------------------------------------------------
def _validate_correlations(
    correlations: list[dict[str, Any]],
    fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate references and matrix shape; repair non-PSD matrices.

    Returns a new list with potentially-repaired entries; never mutates
    its input.
    """
    fields_by_name = {f["name"]: f for f in fields}
    out: list[dict[str, Any]] = []
    for i, entry in enumerate(correlations):
        mode = entry.get("mode")
        if mode == "derived":
            _check_derived(entry, i, fields_by_name)
            out.append(entry)
        elif mode == "multivariate":
            out.append(_check_multivariate(entry, i, fields_by_name))
        else:
            raise SpecValidationError(
                f"correlations[{i}]: unknown mode {mode!r}; expected "
                f"'derived' or 'multivariate'"
            )
    return out


def _check_derived(
    entry: dict[str, Any],
    i: int,
    fields_by_name: dict[str, dict[str, Any]],
) -> None:
    for ref in ("source", "target"):
        name = entry.get(ref)
        if name not in fields_by_name:
            raise SpecValidationError(
                f"correlations[{i}].{ref}={name!r} does not match any field name"
            )
        provider = fields_by_name[name].get("provider")
        if provider not in _NUMERIC_PROVIDERS:
            raise SpecValidationError(
                f"correlations[{i}].{ref}={name!r} must be a numeric field "
                f"(pyfloat/pyint); got provider {provider!r}"
            )


def _check_multivariate(
    entry: dict[str, Any],
    i: int,
    fields_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    field_names = entry.get("fields") or []
    matrix = entry.get("correlation") or []
    n = len(field_names)
    if n < 2:
        raise SpecValidationError(
            f"correlations[{i}]: multivariate needs ≥2 fields, got {n}"
        )
    for name in field_names:
        if name not in fields_by_name:
            raise SpecValidationError(
                f"correlations[{i}]: field {name!r} does not match any field name"
            )
        provider = fields_by_name[name].get("provider")
        if provider not in _NUMERIC_PROVIDERS:
            raise SpecValidationError(
                f"correlations[{i}]: field {name!r} must be numeric "
                f"(pyfloat/pyint); got provider {provider!r}"
            )
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise SpecValidationError(
            f"correlations[{i}]: correlation matrix must be {n}x{n} to match "
            f"{n} fields"
        )

    # Symmetrize then PSD-repair if needed. The LLM can emit slightly
    # invalid matrices (e.g. corr(A,B)=0.9, corr(B,C)=0.9, corr(A,C)=-0.9
    # is geometrically impossible); clipping negative eigenvalues to a
    # tiny positive number gives the nearest PSD matrix.
    M = np.array(matrix, dtype=float)
    M = (M + M.T) / 2
    eigvals, eigvecs = np.linalg.eigh(M)
    if float(eigvals.min()) < -1e-8:
        eigvals = np.clip(eigvals, 1e-8, None)
        M = eigvecs @ np.diag(eigvals) @ eigvecs.T
        d = np.sqrt(np.diag(M))
        M = M / d[:, None] / d[None, :]
        warnings.warn(
            f"correlations[{i}]: correlation matrix was not positive "
            f"semi-definite; auto-repaired to nearest PSD.",
            stacklevel=3,
        )

    repaired = dict(entry)
    repaired["correlation"] = M.tolist()
    return repaired
