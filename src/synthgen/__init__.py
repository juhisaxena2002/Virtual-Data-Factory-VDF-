"""Synthgen — conversational synthetic data generation.

The public API surface is intentionally small. Users import only what they
need from here; everything else is internal.

Example:
    >>> from synthgen import Client
    >>> from synthgen.backends import GeminiBackend
    >>> client = Client(backend=GeminiBackend(api_key="..."))
    >>> records = client.generate("Generate 50 fake orders", count=50)
"""

from ._spec_cache import SpecCache
from .client import Client
from .errors import (
    BackendError,
    BackendResponseError,
    GenerationError,
    SpecValidationError,
    SynthgenError,
)
from .types import (
    Anomaly,
    Correlation,
    DerivedCorrelation,
    Field,
    MultivariateCorrelation,
    Record,
    Spec,
)
from .sinks import HiveMQSink, SinkRouter

__all__ = [
    # Client
    "Client",
    # Cache
    "SpecCache",
    # Types
    "Spec",
    "Field",
    "Anomaly",
    "Correlation",
    "DerivedCorrelation",
    "MultivariateCorrelation",
    "Record",
    # Errors
    "SynthgenError",
    "BackendError",
    "BackendResponseError",
    "SpecValidationError",
    "GenerationError",
    "HiveMQSink",                                 # 
    "SinkRouter",
]

__version__ = "0.2.0"
