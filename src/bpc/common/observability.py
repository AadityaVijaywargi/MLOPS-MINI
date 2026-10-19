"""Structured logging, OpenTelemetry tracing and Prometheus helpers shared by
every service. A correlation id (== run id once a run exists) is bound into a
contextvar and stamped on every log line, span and outgoing request."""
from __future__ import annotations

import contextvars
import logging
import sys
import time
import uuid
from typing import Any

import structlog
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .config import get_settings

CORRELATION_HEADER = "X-Correlation-ID"
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)

_configured = False


def _add_trace_ids(_, __, event_dict: dict) -> dict:
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx and ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    cid = correlation_id_var.get()
    if cid and "correlation_id" not in event_dict:
        event_dict["correlation_id"] = cid
    return event_dict


def setup_logging(service_name: str) -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_trace_ids,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service_name)
    _configured = True


def get_logger(name: str | None = None):
    return structlog.get_logger(name)


def setup_tracing(service_name: str, app: Any = None) -> None:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    endpoint = get_settings().otel_exporter_otlp_endpoint
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics,ready")


def tracer(name: str = "bpc"):
    return trace.get_tracer(name)


def inject_trace_context() -> dict[str, str]:
    carrier: dict[str, str] = {}
    inject(carrier)
    cid = correlation_id_var.get()
    if cid:
        carrier[CORRELATION_HEADER] = cid
    return carrier


def attach_trace_context(carrier: dict[str, str] | None):
    """Attach a propagated context (from a queue message). Returns a token for detach."""
    ctx = extract(carrier or {})
    return otel_context.attach(ctx)


def detach_trace_context(token) -> None:
    otel_context.detach(token)


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx and ctx.is_valid else None


def bind_correlation(correlation_id: str | None = None, **extra: Any) -> str:
    cid = correlation_id or uuid.uuid4().hex
    correlation_id_var.set(cid)
    structlog.contextvars.bind_contextvars(correlation_id=cid, **extra)
    return cid


def outgoing_headers() -> dict[str, str]:
    cid = correlation_id_var.get()
    return {CORRELATION_HEADER: cid} if cid else {}


# ---------------------------------------------------------------- Prometheus
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by route",
    ["service", "method", "route", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["service", "method", "route", "status"])
SERVICE_INFO = Gauge("bpc_service_info", "Static service info", ["service"])
SERVICE_START = Gauge("bpc_service_start_time_seconds", "Unix time the service process started", ["service"])


def mark_service_started(service_name: str) -> None:
    SERVICE_INFO.labels(service_name).set(1)
    SERVICE_START.labels(service_name).set(time.time())


def install_http_middleware(app: Any, service_name: str) -> None:
    from starlette.requests import Request
    from starlette.responses import Response

    @app.middleware("http")
    async def _observe(request: Request, call_next):  # type: ignore[no-redef]
        cid = request.headers.get(CORRELATION_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(service=service_name)
        bind_correlation(cid)
        start = time.perf_counter()
        status = 500
        try:
            response: Response = await call_next(request)
            status = response.status_code
            response.headers[CORRELATION_HEADER] = correlation_id_var.get() or cid
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            if path not in ("/metrics", "/health"):
                elapsed = time.perf_counter() - start
                HTTP_LATENCY.labels(service_name, request.method, path, str(status)).observe(elapsed)
                HTTP_REQUESTS.labels(service_name, request.method, path, str(status)).inc()

    @app.get("/metrics", include_in_schema=False)
    async def _metrics():  # type: ignore[no-redef]
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
