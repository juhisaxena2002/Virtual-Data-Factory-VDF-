"""DatabricksSink — writes streamed records to a Databricks Delta table.

Auto-creates schema and table on first connect if they don't exist.
Uses databricks-sql-connector under the hood.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

Record = dict[str, Any]


class DatabricksSink:
    """Sink that inserts each record as a JSON string into a Databricks Delta table.

    Parameters
    ----------
    host
        Databricks workspace host e.g. ``dbc-08972a14-7690.cloud.databricks.com``.
    token
        Databricks personal access token.
    http_path
        SQL warehouse HTTP path e.g. ``/sql/1.0/warehouses/79855b808a30555c``.
    catalog
        Unity Catalog name. Defaults to ``hive_metastore``.
    schema
        Schema/database name. Defaults to ``synthgen``. Auto-created if missing.
    table
        Table name. Defaults to ``synthgen_stream``. Auto-created if missing.
    batch_size
        Records to buffer before flushing. Default 10.
    """

    def __init__(
        self,
        host: str,
        token: str,
        http_path: str,
        catalog: str = "hive_metastore",
        schema: str = "synthgen",
        table: str = "synthgen_stream",
        batch_size: int = 10,
    ) -> None:
        self._host = host
        self._token = token
        self._http_path = http_path
        self._catalog = catalog
        self._schema = schema
        self._table = table
        self._batch_size = batch_size
        self._conn: Any = None
        self._cursor: Any = None
        self._buffer: list[Record] = []

    # ------------------------------------------------------------------
    # Sink protocol
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Connect to Databricks and ensure schema + table exist."""
        try:
            from databricks import sql as dbsql
        except ImportError as e:
            raise RuntimeError(
                "DatabricksSink requires databricks-sql-connector.\n"
                "Install with: pip install databricks-sql-connector"
            ) from e

        _logger.info("Connecting to Databricks host %s ...", self._host)

        self._conn = dbsql.connect(
            server_hostname=self._host,
            http_path=self._http_path,
            access_token=self._token,
        )
        self._cursor = self._conn.cursor()
        _logger.info("Databricks connected successfully.")

        # Set catalog, create schema and table
        self._cursor.execute(f"USE CATALOG `{self._catalog}`")
        self._cursor.execute(f"CREATE SCHEMA IF NOT EXISTS `{self._schema}`")
        self._cursor.execute(f"USE SCHEMA `{self._schema}`")
        self._cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS `{self._table}` (
                id          BIGINT GENERATED ALWAYS AS IDENTITY,
                record      STRING,
                inserted_at TIMESTAMP
            )
            USING DELTA
        """)

        _logger.info(
            "Ready — streaming into %s.%s.%s",
            self._catalog, self._schema, self._table,
        )

    def write(self, record: Record) -> None:
        """Buffer a record; flush when batch_size is reached."""
        self._buffer.append(record)
        if len(self._buffer) >= self._batch_size:
            self._flush()

    def close(self) -> None:
        """Flush remaining buffer and close connection."""
        self._flush()
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
        _logger.info("Databricks connection closed.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        """Insert buffered records into Databricks one by one."""
        if not self._buffer or self._cursor is None:
            return
        for r in self._buffer:
            payload = json.dumps(r, default=str)
            self._cursor.execute(
                f"INSERT INTO `{self._table}` (record, inserted_at) "
                f"VALUES (?, CURRENT_TIMESTAMP())",
                [payload],
            )
        _logger.info("Flushed %d record(s) to Databricks.", len(self._buffer))
        self._buffer.clear()
