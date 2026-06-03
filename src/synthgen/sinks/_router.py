from __future__ import annotations
from ..types import Record
from ._base import BaseSink

class SinkRouter:
    def __init__(self, sinks: list[BaseSink]) -> None:
        self._sinks = sinks

    def __enter__(self) -> "SinkRouter":
        for sink in self._sinks:
            sink.open()
        return self

    def __exit__(self, *args) -> None:
        for sink in self._sinks:
            sink.close()

    def write(self, record: Record) -> None:
        for sink in self._sinks:
            sink.write(record)
