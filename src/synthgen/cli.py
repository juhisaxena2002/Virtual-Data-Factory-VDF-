# """Command-line interface for synthgen.

# Usage:
#     synthgen "prompt" [--count N] [--seed S] [--output FILE] [--pretty]
#                       [--spec-only] [--backend anthropic|gemini]
#                       [--model MODEL] [--api-key KEY]
#                       [--stream] [--interval SECONDS] [--duration SECONDS]
#                       [--sink hivemq|snowflake|databricks]
#                       [--hivemq-host HOST] [--hivemq-port PORT]
#                       [--hivemq-user USER] [--hivemq-password PASS]
#                       [--hivemq-topic TOPIC]
#                       [--snowflake-account ACCOUNT] [--snowflake-user USER]
#                       [--snowflake-password PASS] [--snowflake-warehouse WH]
#                       [--snowflake-database DB] [--snowflake-schema SCHEMA]
#                       [--snowflake-table TABLE]
#                       [--databricks-host HOST] [--databricks-token TOKEN]
#                       [--databricks-http-path PATH] [--databricks-catalog CAT]
#                       [--databricks-schema SCHEMA] [--databricks-table TABLE]
# """

# from __future__ import annotations

# import argparse
# import json
# import logging
# import os
# import sys
# from typing import Any

# from dotenv import load_dotenv

# load_dotenv()

# from . import __version__
# from ._spec_cache import SpecCache
# from .backends.base import Backend
# from .client import Client
# from .errors import BackendError, SynthgenError


# # ---------------------------------------------------------------------------
# # Backend selection
# # ---------------------------------------------------------------------------

# def _detect_backend() -> str:
#     if os.getenv("ANTHROPIC_API_KEY"):
#         return "anthropic"
#     if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
#         return "gemini"
#     return "anthropic"


# def _build_backend(name: str, model: str | None, api_key: str | None) -> Backend:
#     if name == "anthropic":
#         try:
#             from .backends import AnthropicBackend
#         except ImportError as e:
#             raise BackendError(
#                 "AnthropicBackend requires the anthropic package. "
#                 "Install with: pip install 'synthgen[anthropic]'"
#             ) from e
#         kwargs: dict[str, Any] = {"api_key": api_key}
#         if model:
#             kwargs["model"] = model
#         return AnthropicBackend(**kwargs)

#     if name == "gemini":
#         try:
#             from .backends import GeminiBackend
#         except ImportError as e:
#             raise BackendError(
#                 "GeminiBackend requires the google-genai package. "
#                 "Install with: pip install 'synthgen[gemini]'"
#             ) from e
#         kwargs = {"api_key": api_key}
#         if model:
#             kwargs["model"] = model
#         return GeminiBackend(**kwargs)

#     raise BackendError(
#         f"Unknown backend {name!r}. Supported: anthropic, gemini."
#     )


# # ---------------------------------------------------------------------------
# # Sink builders
# # ---------------------------------------------------------------------------

# def _build_hivemq_sink(args: argparse.Namespace):
#     from .sinks import HiveMQSink
#     missing = []
#     if not args.hivemq_host:
#         missing.append("--hivemq-host")
#     if not args.hivemq_user:
#         missing.append("--hivemq-user")
#     if not args.hivemq_password:
#         missing.append("--hivemq-password")
#     if missing:
#         print(
#             f"synthgen error: --sink hivemq requires: {', '.join(missing)}\n\n"
#             "Example:\n"
#             "  synthgen \"Create persons\" --stream --interval 1 \\\n"
#             "    --sink hivemq \\\n"
#             "    --hivemq-host abc123.s1.eu.hivemq.cloud \\\n"
#             "    --hivemq-user myuser \\\n"
#             "    --hivemq-password mypass",
#             file=sys.stderr,
#         )
#         sys.exit(1)
#     return HiveMQSink(
#         host=args.hivemq_host,
#         port=args.hivemq_port,
#         username=args.hivemq_user,
#         password=args.hivemq_password,
#         topic=args.hivemq_topic,
#         qos=1,
#     )


# def _build_snowflake_sink(args: argparse.Namespace):
#     from .sinks import SnowflakeSink
#     missing = []
#     if not args.snowflake_account:
#         missing.append("--snowflake-account")
#     if not args.snowflake_user:
#         missing.append("--snowflake-user")
#     if not args.snowflake_warehouse:
#         missing.append("--snowflake-warehouse")
#     if not args.snowflake_database:
#         missing.append("--snowflake-database")
#     if missing:
#         print(
#             f"synthgen error: --sink snowflake requires: {', '.join(missing)}\n\n"
#             "Example:\n"
#             "  synthgen \"Create persons\" --stream --interval 1 \\\n"
#             "    --sink snowflake \\\n"
#             "    --snowflake-account PIB20461 \\\n"
#             "    --snowflake-user john@company.com \\\n"
#             "    --snowflake-password mypass \\\n"
#             "    --snowflake-warehouse COMPUTE_WH \\\n"
#             "    --snowflake-database SYNTHGEN_DB",
#             file=sys.stderr,
#         )
#         sys.exit(1)
#     return SnowflakeSink(
#         account=args.snowflake_account,
#         user=args.snowflake_user,
#         password=args.snowflake_password,
#         warehouse=args.snowflake_warehouse,
#         database=args.snowflake_database,
#         schema=args.snowflake_schema,
#         table=args.snowflake_table,
#         batch_size=10,
#     )


# def _build_databricks_sink(args: argparse.Namespace):
#     from .sinks import DatabricksSink
#     missing = []
#     if not args.databricks_host:
#         missing.append("--databricks-host")
#     if not args.databricks_token:
#         missing.append("--databricks-token")
#     if not args.databricks_http_path:
#         missing.append("--databricks-http-path")
#     if missing:
#         print(
#             f"synthgen error: --sink databricks requires: {', '.join(missing)}\n\n"
#             "Example:\n"
#             "  synthgen \"Create persons\" --stream --interval 1 \\\n"
#             "    --sink databricks \\\n"
#             "    --databricks-host dbc-xxxx.cloud.databricks.com \\\n"
#             "    --databricks-token dapiXXXXXXXX \\\n"
#             "    --databricks-http-path /sql/1.0/warehouses/abc123",
#             file=sys.stderr,
#         )
#         sys.exit(1)
#     return DatabricksSink(
#         host=args.databricks_host,
#         token=args.databricks_token,
#         http_path=args.databricks_http_path,
#         catalog=args.databricks_catalog,
#         schema=args.databricks_schema,
#         table=args.databricks_table,
#         batch_size=10,
#     )


# # ---------------------------------------------------------------------------
# # Argument parsing
# # ---------------------------------------------------------------------------

# def _build_parser() -> argparse.ArgumentParser:
#     parser = argparse.ArgumentParser(
#         prog="synthgen",
#         description="Generate synthetic data from a natural-language prompt.",
#         formatter_class=argparse.RawDescriptionHelpFormatter,
#         epilog="""
# examples:
#   # Batch generation
#   synthgen "50 fake e-commerce orders" --count 50 --pretty

#   # Stream to stdout
#   synthgen "IoT sensor readings" --stream --interval 1

#   # Stream to HiveMQ
#   synthgen "Create persons" --stream --interval 1 --sink hivemq --hivemq-host abc.hivemq.cloud --hivemq-user u --hivemq-password p

#   # Stream to Snowflake
#   synthgen "Create persons" --stream --interval 1 --sink snowflake --snowflake-account PIB20461 --snowflake-user u@co.com --snowflake-warehouse WH --snowflake-database DB

#   # Stream to Databricks
#   synthgen "Create persons" --stream --interval 1 --sink databricks --databricks-host dbc-xxx.cloud.databricks.com --databricks-token dapiXXX --databricks-http-path /sql/1.0/warehouses/abc123
# """,
#     )

#     # ---- Core ----
#     parser.add_argument("prompt", help="Natural-language description of the dataset.")
#     parser.add_argument("--count", "-n", type=int, default=100)
#     parser.add_argument("--seed", type=int, default=None)
#     parser.add_argument("--output", "-o", default="-")
#     parser.add_argument("--pretty", action="store_true")
#     parser.add_argument("--spec-only", action="store_true")

#     # ---- Streaming ----
#     parser.add_argument("--stream", action="store_true")
#     parser.add_argument("--interval", type=float, default=None, metavar="SECONDS")
#     parser.add_argument("--duration", type=int, default=None, metavar="SECONDS")

#     # ---- Sink selection ----
#     parser.add_argument(
#         "--sink", choices=["hivemq", "snowflake", "databricks"], default=None,
#         help="Where to push streamed records. Requires --stream.",
#     )

#     # ---- HiveMQ options ----
#     hivemq = parser.add_argument_group("HiveMQ options", "Used when --sink hivemq is set.")
#     hivemq.add_argument("--hivemq-host", default=None, metavar="HOST")
#     hivemq.add_argument("--hivemq-port", type=int, default=8883, metavar="PORT")
#     hivemq.add_argument("--hivemq-user", default=None, metavar="USER")
#     hivemq.add_argument("--hivemq-password", default=None, metavar="PASS")
#     hivemq.add_argument("--hivemq-topic", default="synthgen/stream", metavar="TOPIC")

#     # ---- Snowflake options ----
#     sf = parser.add_argument_group("Snowflake options", "Used when --sink snowflake is set.")
#     sf.add_argument("--snowflake-account", default=None, metavar="ACCOUNT")
#     sf.add_argument("--snowflake-user", default=None, metavar="USER")
#     sf.add_argument("--snowflake-password", default=None, metavar="PASS",
#                     help="Omit for Azure AD browser login.")
#     sf.add_argument("--snowflake-warehouse", default=None, metavar="WH")
#     sf.add_argument("--snowflake-database", default=None, metavar="DB")
#     sf.add_argument("--snowflake-schema", default="PUBLIC", metavar="SCHEMA")
#     sf.add_argument("--snowflake-table", default="SYNTHGEN_STREAM", metavar="TABLE")

#     # ---- Databricks options ----
#     db = parser.add_argument_group("Databricks options", "Used when --sink databricks is set.")
#     db.add_argument("--databricks-host", default=None, metavar="HOST",
#                     help="e.g. dbc-08972a14-7690.cloud.databricks.com")
#     db.add_argument("--databricks-token", default=None, metavar="TOKEN",
#                     help="Personal access token (dapiXXXX...)")
#     db.add_argument("--databricks-http-path", default=None, metavar="PATH",
#                     help="e.g. /sql/1.0/warehouses/abc123")
#     db.add_argument("--databricks-catalog", default="hive_metastore", metavar="CATALOG",
#                     help="Unity Catalog name. Default: hive_metastore")
#     db.add_argument("--databricks-schema", default="synthgen", metavar="SCHEMA",
#                     help="Schema name. Default: synthgen. Auto-created if missing.")
#     db.add_argument("--databricks-table", default="synthgen_stream", metavar="TABLE",
#                     help="Table name. Default: synthgen_stream. Auto-created if missing.")

#     # ---- Backend ----
#     parser.add_argument("--correlation",
#                         choices=["auto", "independent", "derived", "multivariate"],
#                         default="auto")
#     parser.add_argument("--backend", choices=["anthropic", "gemini"], default=None)
#     parser.add_argument("--model", default=None)
#     parser.add_argument("--api-key", default=None)
#     parser.add_argument("--no-cache", action="store_true", dest="no_cache")
#     parser.add_argument("--cache-threshold", type=float, default=None, metavar="0..1")
#     parser.add_argument("--verbose", "-v", action="count", default=0)
#     parser.add_argument("--version", action="version", version=f"synthgen {__version__}")
#     return parser


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def _configure_logging(verbosity: int) -> None:
#     level = logging.DEBUG if verbosity >= 1 else logging.INFO
#     handler = logging.StreamHandler(sys.stderr)
#     handler.setFormatter(logging.Formatter("synthgen: %(message)s"))
#     syn_logger = logging.getLogger("synthgen")
#     syn_logger.setLevel(level)
#     syn_logger.handlers.clear()
#     syn_logger.addHandler(handler)
#     syn_logger.propagate = False


# def _build_client(args: argparse.Namespace) -> Client:
#     backend_name = args.backend or _detect_backend()
#     backend = _build_backend(backend_name, model=args.model, api_key=args.api_key)
#     cache: bool | SpecCache | None
#     if args.no_cache:
#         cache = None
#     elif args.cache_threshold is not None:
#         cache = SpecCache(threshold=args.cache_threshold)
#     else:
#         cache = True
#     return Client(backend=backend, cache=cache)


# def _serialize(obj: Any, pretty: bool) -> str:
#     return json.dumps(obj, indent=2 if pretty else None, default=str, ensure_ascii=False)


# def _write(text: str, output: str) -> None:
#     if output == "-":
#         sys.stdout.write(text)
#         if not text.endswith("\n"):
#             sys.stdout.write("\n")
#     else:
#         with open(output, "w", encoding="utf-8") as f:
#             f.write(text)
#             if not text.endswith("\n"):
#                 f.write("\n")


# # ---------------------------------------------------------------------------
# # Stream runner
# # ---------------------------------------------------------------------------

# def _run_stream(client: Client, args: argparse.Namespace) -> None:
#     from .sinks import SinkRouter

#     records = client.stream(
#         args.prompt,
#         interval_sec=args.interval,
#         duration_sec=args.duration,
#         seed=args.seed,
#         correlation_mode=args.correlation,
#     )

#     sinks = []
#     if args.sink == "hivemq":
#         sinks.append(_build_hivemq_sink(args))
#     elif args.sink == "snowflake":
#         sinks.append(_build_snowflake_sink(args))
#     elif args.sink == "databricks":
#         sinks.append(_build_databricks_sink(args))

#     if sinks:
#         with SinkRouter(sinks) as router:
#             print(f"Streaming to {args.sink.upper()}... (Ctrl+C to stop)", file=sys.stderr)
#             for record in records:
#                 router.write(record)
#                 sys.stdout.write(_serialize(record, pretty=args.pretty))
#                 sys.stdout.write("\n")
#                 sys.stdout.flush()
#     else:
#         use_stdout = args.output == "-"
#         out = sys.stdout if use_stdout else open(args.output, "w", encoding="utf-8")
#         try:
#             for record in records:
#                 out.write(_serialize(record, pretty=args.pretty))
#                 out.write("\n")
#                 out.flush()
#         finally:
#             if not use_stdout:
#                 out.close()


# # ---------------------------------------------------------------------------
# # Entry point
# # ---------------------------------------------------------------------------

# def main(argv: list[str] | None = None) -> int:
#     parser = _build_parser()
#     args = parser.parse_args(argv)
#     _configure_logging(args.verbose)

#     if args.sink and not args.stream:
#         print(f"synthgen error: --sink {args.sink} requires --stream", file=sys.stderr)
#         return 1

#     try:
#         client = _build_client(args)
#         if args.spec_only:
#             output = client.compile_spec(
#                 args.prompt, correlation_mode=args.correlation,
#             ).to_dict()
#         elif args.stream:
#             _run_stream(client, args)
#             return 0
#         else:
#             output = client.generate(
#                 args.prompt,
#                 count=args.count,
#                 seed=args.seed,
#                 correlation_mode=args.correlation,
#             )
#     except SynthgenError as e:
#         print(f"synthgen error: {e}", file=sys.stderr)
#         return e.exit_code
#     except KeyboardInterrupt:
#         print("\nInterrupted.", file=sys.stderr)
#         return 130

#     _write(_serialize(output, pretty=args.pretty), args.output)
#     return 0


# if __name__ == "__main__":
#     sys.exit(main())

"""Command-line interface for synthgen.

Usage:
    synthgen "prompt" [--count N] [--seed S] [--output FILE] [--pretty]
                      [--spec-only] [--backend anthropic|gemini]
                      [--model MODEL] [--api-key KEY]
                      [--stream] [--interval SECONDS] [--duration SECONDS]
                      [--sink hivemq|snowflake|databricks|public-api]
                      [--hivemq-host HOST] [--hivemq-port PORT]
                      [--hivemq-user USER] [--hivemq-password PASS]
                      [--hivemq-topic TOPIC]
                      [--snowflake-account ACCOUNT] [--snowflake-user USER]
                      [--snowflake-password PASS] [--snowflake-warehouse WH]
                      [--snowflake-database DB] [--snowflake-schema SCHEMA]
                      [--snowflake-table TABLE]
                      [--databricks-host HOST] [--databricks-token TOKEN]
                      [--databricks-http-path PATH] [--databricks-catalog CAT]
                      [--databricks-schema SCHEMA] [--databricks-table TABLE]
                      [--api-url URL] [--api-auth-type none|bearer|api_key]
                      [--api-auth-value TOKEN] [--api-format json|ndjson]
                      [--api-headers JSON]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from . import __version__
from ._spec_cache import SpecCache
from .backends.base import Backend
from .client import Client
from .errors import BackendError, SynthgenError


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _detect_backend() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "anthropic"


def _build_backend(name: str, model: str | None, api_key: str | None) -> Backend:
    if name == "anthropic":
        try:
            from .backends import AnthropicBackend
        except ImportError as e:
            raise BackendError(
                "AnthropicBackend requires the anthropic package. "
                "Install with: pip install 'synthgen[anthropic]'"
            ) from e
        kwargs: dict[str, Any] = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        return AnthropicBackend(**kwargs)

    if name == "gemini":
        try:
            from .backends import GeminiBackend
        except ImportError as e:
            raise BackendError(
                "GeminiBackend requires the google-genai package. "
                "Install with: pip install 'synthgen[gemini]'"
            ) from e
        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        return GeminiBackend(**kwargs)

    raise BackendError(
        f"Unknown backend {name!r}. Supported: anthropic, gemini."
    )


# ---------------------------------------------------------------------------
# Sink builders
# ---------------------------------------------------------------------------

def _build_hivemq_sink(args: argparse.Namespace):
    from .sinks import HiveMQSink
    missing = []
    if not args.hivemq_host:
        missing.append("--hivemq-host")
    if not args.hivemq_user:
        missing.append("--hivemq-user")
    if not args.hivemq_password:
        missing.append("--hivemq-password")
    if missing:
        print(
            f"synthgen error: --sink hivemq requires: {', '.join(missing)}\n\n"
            "Example:\n"
            "  synthgen \"Create persons\" --stream --interval 1 \\\n"
            "    --sink hivemq \\\n"
            "    --hivemq-host abc123.s1.eu.hivemq.cloud \\\n"
            "    --hivemq-user myuser \\\n"
            "    --hivemq-password mypass",
            file=sys.stderr,
        )
        sys.exit(1)
    return HiveMQSink(
        host=args.hivemq_host,
        port=args.hivemq_port,
        username=args.hivemq_user,
        password=args.hivemq_password,
        topic=args.hivemq_topic,
        qos=1,
    )




def _build_public_api_sink(args: argparse.Namespace):
    from .sinks import PublicAPISink

    missing = []
    if not args.api_url:
        missing.append("--api-url        (destination endpoint, e.g. https://webhook.site/your-uuid)")
    if not args.api_auth_type:
        missing.append("--api-auth-type  (none | bearer | api_key)")
    if not args.api_format:
        missing.append("--api-format     (json | ndjson)")

    if missing:
        print(
            "synthgen error: --sink public-api requires all three of:\n"
            + "\n".join(f"  {m}" for m in missing)
            + "\n\n"
            "Examples:\n"
            "  # No auth (Webhook.site)\n"
            "  synthgen \"IoT sensors\" --stream --sink public-api --api-url https://webhook.site/your-uuid --api-auth-type none --api-format json\n\n"
            "  # Bearer token\n"
            "  synthgen \"IoT sensors\" --stream --sink public-api --api-url https://api.example.com/ingest --api-auth-type bearer --api-auth-value mytoken --api-format json\n\n"
            "  # API key + ndjson (Elasticsearch)\n"
            "  synthgen \"IoT sensors\" --stream --sink public-api --api-url https://my-es.cloud:9243/synthgen/_doc --api-auth-type api_key --api-auth-value mykey --api-format ndjson",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.api_auth_type != "none" and not args.api_auth_value:
        print(
            f"synthgen error: --api-auth-type {args.api_auth_type} also requires --api-auth-value <token>",
            file=sys.stderr,
        )
        sys.exit(1)

    custom_headers: dict[str, str] | None = None
    if args.api_headers:
        try:
            custom_headers = json.loads(args.api_headers)
            if not isinstance(custom_headers, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            print(
                "synthgen error: --api-headers must be a JSON object. "
                "Example: --api-headers '{\"X-Index\": \"main\"}'",
                file=sys.stderr,
            )
            sys.exit(1)

    return PublicAPISink(
        url=args.api_url,
        auth_type=args.api_auth_type,
        auth_value=args.api_auth_value,
        data_format=args.api_format,
        custom_headers=custom_headers,
    )

def _build_snowflake_sink(args: argparse.Namespace):
    from .sinks import SnowflakeSink
    missing = []
    if not args.snowflake_account:
        missing.append("--snowflake-account")
    if not args.snowflake_user:
        missing.append("--snowflake-user")
    if not args.snowflake_warehouse:
        missing.append("--snowflake-warehouse")
    if not args.snowflake_database:
        missing.append("--snowflake-database")
    if missing:
        print(
            f"synthgen error: --sink snowflake requires: {', '.join(missing)}\n\n"
            "Example:\n"
            "  synthgen \"Create persons\" --stream --interval 1 \\\n"
            "    --sink snowflake \\\n"
            "    --snowflake-account PIB20461 \\\n"
            "    --snowflake-user john@company.com \\\n"
            "    --snowflake-password mypass \\\n"
            "    --snowflake-warehouse COMPUTE_WH \\\n"
            "    --snowflake-database SYNTHGEN_DB",
            file=sys.stderr,
        )
        sys.exit(1)
    return SnowflakeSink(
        account=args.snowflake_account,
        user=args.snowflake_user,
        password=args.snowflake_password,
        warehouse=args.snowflake_warehouse,
        database=args.snowflake_database,
        schema=args.snowflake_schema,
        table=args.snowflake_table,
        batch_size=10,
    )


def _build_databricks_sink(args: argparse.Namespace):
    from .sinks import DatabricksSink
    missing = []
    if not args.databricks_host:
        missing.append("--databricks-host")
    if not args.databricks_token:
        missing.append("--databricks-token")
    if not args.databricks_http_path:
        missing.append("--databricks-http-path")
    if missing:
        print(
            f"synthgen error: --sink databricks requires: {', '.join(missing)}\n\n"
            "Example:\n"
            "  synthgen \"Create persons\" --stream --interval 1 \\\n"
            "    --sink databricks \\\n"
            "    --databricks-host dbc-xxxx.cloud.databricks.com \\\n"
            "    --databricks-token dapiXXXXXXXX \\\n"
            "    --databricks-http-path /sql/1.0/warehouses/abc123",
            file=sys.stderr,
        )
        sys.exit(1)
    return DatabricksSink(
        host=args.databricks_host,
        token=args.databricks_token,
        http_path=args.databricks_http_path,
        catalog=args.databricks_catalog,
        schema=args.databricks_schema,
        table=args.databricks_table,
        batch_size=10,
    )


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synthgen",
        description="Generate synthetic data from a natural-language prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Batch generation
  synthgen "50 fake e-commerce orders" --count 50 --pretty

  # Stream to stdout
  synthgen "IoT sensor readings" --stream --interval 1

  # Stream to HiveMQ
  synthgen "Create persons" --stream --interval 1 --sink hivemq --hivemq-host abc.hivemq.cloud --hivemq-user u --hivemq-password p

  # Stream to Snowflake
  synthgen "Create persons" --stream --interval 1 --sink snowflake --snowflake-account PIB20461 --snowflake-user u@co.com --snowflake-warehouse WH --snowflake-database DB

  # Stream to Databricks
  synthgen "Create persons" --stream --interval 1 --sink databricks --databricks-host dbc-xxx.cloud.databricks.com --databricks-token dapiXXX --databricks-http-path /sql/1.0/warehouses/abc123

  # Stream to a public HTTP API
  synthgen "IoT sensors" --stream --interval 1 --sink public-api --api-url https://webhook.site/your-uuid --api-auth-type none --api-format json

  # Stream to a public HTTP API with bearer token
  synthgen "IoT sensors" --stream --interval 1 --sink public-api --api-url https://api.example.com/ingest --api-auth-type bearer --api-auth-value mytoken --api-format json
""",
    )

    # ---- Core ----
    parser.add_argument("prompt", help="Natural-language description of the dataset.")
    parser.add_argument("--count", "-n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output", "-o", default="-")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--spec-only", action="store_true")

    # ---- Streaming ----
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--interval", type=float, default=None, metavar="SECONDS")
    parser.add_argument("--duration", type=int, default=None, metavar="SECONDS")

    # ---- Sink selection ----
    parser.add_argument(
        "--sink", choices=["hivemq", "snowflake", "databricks", "public-api"], default=None,
        help="Where to push streamed records. Requires --stream.",
    )

    # ---- HiveMQ options ----
    hivemq = parser.add_argument_group("HiveMQ options", "Used when --sink hivemq is set.")
    hivemq.add_argument("--hivemq-host", default=None, metavar="HOST")
    hivemq.add_argument("--hivemq-port", type=int, default=8883, metavar="PORT")
    hivemq.add_argument("--hivemq-user", default=None, metavar="USER")
    hivemq.add_argument("--hivemq-password", default=None, metavar="PASS")
    hivemq.add_argument("--hivemq-topic", default="synthgen/stream", metavar="TOPIC")

    # ---- Snowflake options ----
    sf = parser.add_argument_group("Snowflake options", "Used when --sink snowflake is set.")
    sf.add_argument("--snowflake-account", default=None, metavar="ACCOUNT")
    sf.add_argument("--snowflake-user", default=None, metavar="USER")
    sf.add_argument("--snowflake-password", default=None, metavar="PASS",
                    help="Omit for Azure AD browser login.")
    sf.add_argument("--snowflake-warehouse", default=None, metavar="WH")
    sf.add_argument("--snowflake-database", default=None, metavar="DB")
    sf.add_argument("--snowflake-schema", default="PUBLIC", metavar="SCHEMA")
    sf.add_argument("--snowflake-table", default="SYNTHGEN_STREAM", metavar="TABLE")

    # ---- Databricks options ----
    db = parser.add_argument_group("Databricks options", "Used when --sink databricks is set.")
    db.add_argument("--databricks-host", default=None, metavar="HOST",
                    help="e.g. dbc-08972a14-7690.cloud.databricks.com")
    db.add_argument("--databricks-token", default=None, metavar="TOKEN",
                    help="Personal access token (dapiXXXX...)")
    db.add_argument("--databricks-http-path", default=None, metavar="PATH",
                    help="e.g. /sql/1.0/warehouses/abc123")
    db.add_argument("--databricks-catalog", default="hive_metastore", metavar="CATALOG",
                    help="Unity Catalog name. Default: hive_metastore")
    db.add_argument("--databricks-schema", default="synthgen", metavar="SCHEMA",
                    help="Schema name. Default: synthgen. Auto-created if missing.")
    db.add_argument("--databricks-table", default="synthgen_stream", metavar="TABLE",
                    help="Table name. Default: synthgen_stream. Auto-created if missing.")


    # ---- Public API options ----
    pa = parser.add_argument_group("Public API options", "Used when --sink public-api is set. POSTs each record over HTTP.")
    pa.add_argument("--api-url", default=None, metavar="URL",
                    help="Destination endpoint URL.")
    pa.add_argument("--api-auth-type", choices=["none", "bearer", "api_key"], default=None, metavar="TYPE",
                    help="Required with --sink public-api. Auth type: none | bearer | api_key.")
    pa.add_argument("--api-auth-value", default=None, metavar="TOKEN",
                    help="Token or key. Required for bearer/api_key.")
    pa.add_argument("--api-format", choices=["json", "ndjson"], default=None, metavar="FORMAT",
                    help="Required with --sink public-api. Payload format: json | ndjson.")
    pa.add_argument("--api-headers", default=None, metavar="JSON",
                    help='Extra headers as JSON string. Example: \'{"X-Index": "main"}\'')

    # ---- Backend ----
    parser.add_argument("--correlation",
                        choices=["auto", "independent", "derived", "multivariate"],
                        default="auto")
    parser.add_argument("--backend", choices=["anthropic", "gemini"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--no-cache", action="store_true", dest="no_cache")
    parser.add_argument("--cache-threshold", type=float, default=None, metavar="0..1")
    parser.add_argument("--verbose", "-v", action="count", default=0)
    parser.add_argument("--version", action="version", version=f"synthgen {__version__}")
    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configure_logging(verbosity: int) -> None:
    level = logging.DEBUG if verbosity >= 1 else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("synthgen: %(message)s"))
    syn_logger = logging.getLogger("synthgen")
    syn_logger.setLevel(level)
    syn_logger.handlers.clear()
    syn_logger.addHandler(handler)
    syn_logger.propagate = False


def _build_client(args: argparse.Namespace) -> Client:
    backend_name = args.backend or _detect_backend()
    backend = _build_backend(backend_name, model=args.model, api_key=args.api_key)
    cache: bool | SpecCache | None
    if args.no_cache:
        cache = None
    elif args.cache_threshold is not None:
        cache = SpecCache(threshold=args.cache_threshold)
    else:
        cache = True
    return Client(backend=backend, cache=cache)


def _serialize(obj: Any, pretty: bool) -> str:
    return json.dumps(obj, indent=2 if pretty else None, default=str, ensure_ascii=False)


def _write(text: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")


# ---------------------------------------------------------------------------
# Stream runner
# ---------------------------------------------------------------------------

def _run_stream(client: Client, args: argparse.Namespace) -> None:
    from .sinks import SinkRouter

    records = client.stream(
        args.prompt,
        interval_sec=args.interval,
        duration_sec=args.duration,
        seed=args.seed,
        correlation_mode=args.correlation,
    )

    sinks = []
    if args.sink == "hivemq":
        sinks.append(_build_hivemq_sink(args))
    elif args.sink == "snowflake":
        sinks.append(_build_snowflake_sink(args))
    elif args.sink == "databricks":
        sinks.append(_build_databricks_sink(args))
    elif args.sink == "public-api":
        sinks.append(_build_public_api_sink(args))

    if sinks:
        with SinkRouter(sinks) as router:
            print(f"Streaming to {args.sink.upper()}... (Ctrl+C to stop)", file=sys.stderr)
            for record in records:
                router.write(record)
                sys.stdout.write(_serialize(record, pretty=args.pretty))
                sys.stdout.write("\n")
                sys.stdout.flush()
    else:
        use_stdout = args.output == "-"
        out = sys.stdout if use_stdout else open(args.output, "w", encoding="utf-8")
        try:
            for record in records:
                out.write(_serialize(record, pretty=args.pretty))
                out.write("\n")
                out.flush()
        finally:
            if not use_stdout:
                out.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    if args.sink and not args.stream:
        print(f"synthgen error: --sink {args.sink} requires --stream", file=sys.stderr)
        return 1

    try:
        client = _build_client(args)
        if args.spec_only:
            output = client.compile_spec(
                args.prompt, correlation_mode=args.correlation,
            ).to_dict()
        elif args.stream:
            _run_stream(client, args)
            return 0
        else:
            output = client.generate(
                args.prompt,
                count=args.count,
                seed=args.seed,
                correlation_mode=args.correlation,
            )
    except SynthgenError as e:
        print(f"synthgen error: {e}", file=sys.stderr)
        return e.exit_code
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    _write(_serialize(output, pretty=args.pretty), args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
