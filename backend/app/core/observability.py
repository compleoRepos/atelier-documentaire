from __future__ import annotations

import hmac
import time
import uuid

from fastapi import HTTPException, Request
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    ProcessCollector,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        self.requests = Counter(
            "translator_http_requests_total",
            "Requêtes HTTP sans données personnelles",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "translator_http_duration_seconds",
            "Latence HTTP",
            ["method", "route"],
            registry=self.registry,
        )


class RequestTelemetry(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        # UUID généré par le serveur : jamais un header externe non fiable dans logs.
        request_id = str(uuid.uuid4())
        try:
            response = await call_next(request)
        except Exception:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            request.app.state.metrics.requests.labels(request.method, route, "500").inc()
            raise
        route = getattr(request.scope.get("route"), "path", "unmatched")
        metrics = request.app.state.metrics
        metrics.requests.labels(request.method, route, str(response.status_code)).inc()
        metrics.duration.labels(request.method, route).observe(time.perf_counter() - started)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/api/") else "no-cache"
        )
        return response


def add_metrics_routes(app):
    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request):
        settings = app.state.settings
        if not settings.metrics_enabled:
            raise HTTPException(404)
        required = settings.metrics_token
        authorization = request.headers.get("Authorization", "")
        if required and not hmac.compare_digest(authorization, f"Bearer {required}"):
            raise HTTPException(401, "Accès métriques refusé")
        if not required and settings.environment.lower() not in {"local", "dev", "test"}:
            raise HTTPException(503, "Accès métriques non configuré")
        return Response(
            generate_latest(app.state.metrics.registry), media_type="text/plain; version=0.0.4"
        )
