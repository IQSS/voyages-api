import os
import time

from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry
from prometheus_client import Counter
from prometheus_client import GCCollector
from prometheus_client import Histogram
from prometheus_client import PlatformCollector
from prometheus_client import ProcessCollector
from prometheus_client import generate_latest
from prometheus_client import multiprocess


_REQUEST_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
)

REQUEST_COUNT = Counter(
    "sv_http_requests_total",
    "Total HTTP requests handled by Slave Voyages services.",
    ("service", "framework", "endpoint", "method", "status"),
)

REQUEST_LATENCY = Histogram(
    "sv_http_request_duration_seconds",
    "HTTP request latency for Slave Voyages services.",
    ("service", "framework", "endpoint", "method"),
    buckets=_REQUEST_BUCKETS,
)


def _endpoint_label(request) -> str:
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is not None:
        view_name = getattr(resolver_match, "view_name", "") or ""
        if view_name:
            return view_name
        route = getattr(resolver_match, "route", "") or ""
        if route:
            return route
    path = getattr(request, "path", "") or "/"
    if path.startswith("/"):
        return path
    return f"/{path}"


class PrometheusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        status_code = "500"
        try:
            response = self.get_response(request)
            status_code = str(getattr(response, "status_code", 500))
            return response
        finally:
            endpoint = _endpoint_label(request)
            method = str(getattr(request, "method", "GET") or "GET").upper()
            REQUEST_COUNT.labels(
                service="voyages-api",
                framework="django",
                endpoint=endpoint,
                method=method,
                status=status_code,
            ).inc()
            REQUEST_LATENCY.labels(
                service="voyages-api",
                framework="django",
                endpoint=endpoint,
                method=method,
            ).observe(time.perf_counter() - started_at)


def metrics_view(_request):
    registry = CollectorRegistry()
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "").strip()
    if multiproc_dir:
        multiprocess.MultiProcessCollector(registry)
    else:
        ProcessCollector(registry=registry)
        PlatformCollector(registry=registry)
        GCCollector(registry=registry)
    return HttpResponse(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)
