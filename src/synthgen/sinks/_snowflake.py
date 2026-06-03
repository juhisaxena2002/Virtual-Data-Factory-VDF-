"""SnowflakeSink — writes streamed records to a Snowflake table.

Handles schema + table auto-creation on first connect, so the client
never needs to touch SQL manually.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

Record = dict[str, Any]


class SnowflakeSink:
    """Sink that inserts each record as a VARIANT row into Snowflake.

    Parameters
    ----------
    account
        Snowflake account identifier e.g. ``PIB20461``.
    user
        Snowflake username e.g. ``JUHI.SAXENA@ASCENTT.COM``.
    warehouse
        Warehouse to use e.g. ``SNOWFLAKE_LEARNING_WH``.
    database
        Target database e.g. ``SNOWFLAKE_LEARNING_DB``.
    schema
        Target schema. Defaults to ``SYNTHGEN``. Auto-created if missing.
    table
        Target table. Defaults to ``SYNTHGEN_STREAM``. Auto-created if missing.
    password
        Optional password. If ``None``, uses ``externalbrowser`` (Azure AD /
        SSO login via browser popup).
    batch_size
        Records to buffer before flushing to Snowflake. Default 10.
    """

    def __init__(
        self,
        account: str,
        user: str,
        warehouse: str,
        database: str,
        schema: str = "SYNTHGEN",
        table: str = "SYNTHGEN_STREAM",
        password: str | None = None,
        batch_size: int = 10,
    ) -> None:
        self._account = account
        self._user = user
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._table = table
        self._password = password
        self._batch_size = batch_size
        self._conn: Any = None
        self._cursor: Any = None
        self._buffer: list[Record] = []

    # ------------------------------------------------------------------
    # Sink protocol
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Connect to Snowflake and ensure schema + table exist."""
        try:
            import snowflake.connector
        except ImportError as e:
            raise RuntimeError(
                "SnowflakeSink requires snowflake-connector-python.\n"
                "Install with: pip install snowflake-connector-python"
            ) from e

        authenticator = "externalbrowser" if self._password is None else "snowflake"

        _logger.info("Connecting to Snowflake account %s ...", self._account)
        if authenticator == "externalbrowser":
            _logger.info(
                "A browser window will open for Azure AD login — "
                "please sign in with %s", self._user
            )

        self._conn = snowflake.connector.connect(
            account=self._account,
            user=self._user,
            authenticator=authenticator,
            password=self._password,
            warehouse=self._warehouse,
            database=self._database,
        )
        self._cursor = self._conn.cursor()
        _logger.info("Snowflake connected successfully.")

        # Use schema (already exists)
        # Use database and schema
        # Use database, schema and warehouse
        self._cursor.execute(f"USE DATABASE {self._database}")
        self._cursor.execute(f"USE SCHEMA {self._schema}")
        self._cursor.execute(f"USE WAREHOUSE {self._warehouse}")

        # Try to auto-create table — skip if no permission (assume it exists)
        try:
                self._cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._table} (
                        id          NUMBER AUTOINCREMENT PRIMARY KEY,
                        record      VARIANT,
                        inserted_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                    )
                """)
                self._conn.commit()
        except Exception:
                _logger.warning(
                    "Could not auto-create table %s — assuming it already exists.",
                    self._table,
                )

        _logger.info(
            "Ready — streaming into %s.%s.%s",
            self._database, self._schema, self._table,
        )

    def write(self, record: Record) -> None:
        """Buffer a record; flush automatically when batch_size is reached."""
        self._buffer.append(record)
        if len(self._buffer) >= self._batch_size:
            self._flush()

    def close(self) -> None:
        """Flush any remaining buffered records and close the connection."""
        self._flush()
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
        _logger.info("Snowflake connection closed.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        """Insert all buffered records into Snowflake one by one."""
        if not self._buffer or self._cursor is None:
            return
        for r in self._buffer:
            payload = json.dumps(r, default=str)
            self._cursor.execute(
                f"INSERT INTO {self._table} (record) SELECT PARSE_JSON(%s)",
                (payload,)
            )
        self._conn.commit()
        _logger.info("Flushed %d record(s) to Snowflake.", len(self._buffer))
        self._buffer.clear()
