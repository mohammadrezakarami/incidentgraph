from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, cast
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from incidentgraph.lab_runtime import (
    ActiveFault,
    FaultCommand,
    FaultState,
    LabMetrics,
    LabServiceSettings,
    bounded_cpu_work,
    build_event_logger,
    build_tracer,
    log_event,
    span_context_fields,
    verify_control_token,
)


class LabOrder(BaseModel):
    order_id: str = Field(pattern=r"^ord-[a-z0-9-]{1,80}$", max_length=84)
    amount_cents: int = Field(ge=100, le=100_000)
    payment_token: str = Field(pattern=r"^tok_test_[0-9]{1,3}$", max_length=16)


class LabResult(BaseModel):
    order_id: str
    status: str
    service: str
    deployment_version: str


def create_lab_app(settings: LabServiceSettings | None = None) -> FastAPI:
    service_settings = settings or LabServiceSettings()  # type: ignore[call-arg]
    metrics = LabMetrics(
        service_settings.service,
        service_settings.deployment_version,
    )
    fault_state = FaultState(service_settings.fault_max_seconds)
    event_logger = build_event_logger(service_settings.service, service_settings.log_dir)
    tracer = build_tracer(service_settings.service, service_settings.trace_dir)
    base_version = service_settings.deployment_version

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.http = httpx.AsyncClient(timeout=service_settings.http_timeout_seconds)
        app.state.pool = None
        app.state.redis = None
        app.state.pool_holders = set()
        if service_settings.service in {"checkout", "payments"}:
            pool = cast(
                AsyncConnectionPool[AsyncConnection[tuple[Any, ...]]],
                AsyncConnectionPool(
                    conninfo=service_settings.database_dsn.get_secret_value(),
                    min_size=1,
                    max_size=service_settings.db_pool_size,
                    open=False,
                ),
            )
            await pool.open(wait=True, timeout=15)
            app.state.pool = pool
            metrics.set_pool_size(service_settings.db_pool_size)
        if service_settings.service == "payments":
            redis_client = Redis.from_url(
                service_settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            await redis_client.ping()
            app.state.redis = redis_client
        log_event(
            event_logger,
            "service.started",
            service=service_settings.service,
            environment=service_settings.environment,
            deployment_version=base_version,
        )
        yield
        holders: set[asyncio.Task[None]] = app.state.pool_holders
        for task in holders:
            task.cancel()
        if holders:
            await asyncio.gather(*holders, return_exceptions=True)
        redis_to_close: Redis | None = app.state.redis
        if redis_to_close is not None:
            await redis_to_close.aclose()
        pool_to_close: AsyncConnectionPool[AsyncConnection[tuple[Any, ...]]] | None = app.state.pool
        if pool_to_close is not None:
            await pool_to_close.close()
        await app.state.http.aclose()

    app = FastAPI(
        title=f"IncidentGraph lab {service_settings.service}",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = service_settings
    app.state.metrics = metrics
    app.state.faults = fault_state

    @app.middleware("http")
    async def instrument_request(request: Request, call_next: Any) -> Response:
        if request.url.path.startswith("/__control"):
            return cast(Response, await call_next(request))
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter()
        parent_context = extract(request.headers)
        status_code = 500
        route = request.url.path
        with tracer.start_as_current_span(
            f"{service_settings.service}.http",
            context=parent_context,
            attributes={
                "http.request.method": request.method,
                "http.route": route,
                "service.name": service_settings.service,
            },
        ) as span:
            try:
                response = cast(Response, await call_next(request))
                status_code = response.status_code
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                elapsed = time.perf_counter() - started
                route_object = request.scope.get("route")
                route = getattr(route_object, "path", route)
                status_class = f"{status_code // 100}xx"
                metrics.requests.labels(
                    service_settings.service,
                    route,
                    status_class,
                ).inc()
                metrics.request_duration.labels(
                    service_settings.service,
                    route,
                ).observe(elapsed)
                active = fault_state.current()
                current_version = _current_version(active, base_version)
                log_event(
                    event_logger,
                    "http.request",
                    service=service_settings.service,
                    environment=service_settings.environment,
                    request_id=request_id,
                    route=route,
                    method=request.method,
                    status_code=status_code,
                    duration_ms=round(elapsed * 1_000, 3),
                    deployment_version=current_version,
                    **span_context_fields(),
                )
                span.set_attribute("http.response.status_code", status_code)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))
            response.headers["X-Request-ID"] = request_id
            trace_fields = span_context_fields()
            response.headers["X-Trace-ID"] = trace_fields["trace_id"]
            return response

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok", "service": service_settings.service}

    @app.get("/health/ready")
    async def ready(request: Request) -> dict[str, str]:
        if service_settings.service in {"checkout", "payments"}:
            pool = _pool(request)
            async with pool.connection(timeout=1) as connection:
                await connection.execute("SELECT 1")
        if service_settings.service == "payments":
            redis_client = _redis(request)
            await redis_client.ping()
        return {"status": "ready", "service": service_settings.service}

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        active = fault_state.current()
        if active is not None and active.command.kind == "metrics_disabled":
            raise HTTPException(status_code=503, detail="metrics temporarily unavailable")
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    @app.post("/__control/fault")
    async def apply_fault(
        command: FaultCommand,
        request: Request,
        token: Annotated[str | None, Header(alias="X-Lab-Control-Token")] = None,
    ) -> dict[str, str | int]:
        _authorize_control(token, service_settings)
        _validate_fault_for_service(command, service_settings)
        active = fault_state.apply(command)
        if command.kind == "deployment_regression":
            metrics.set_deployment(command.deployment_version or base_version)
        if command.kind == "pool_exhaustion":
            await _start_pool_holders(request, active, metrics)
        return {
            "status": "applied",
            "service": service_settings.service,
            "duration_seconds": command.duration_seconds,
        }

    @app.delete("/__control/fault")
    async def reset_fault(
        request: Request,
        token: Annotated[str | None, Header(alias="X-Lab-Control-Token")] = None,
    ) -> dict[str, str]:
        _authorize_control(token, service_settings)
        fault_state.reset()
        metrics.set_deployment(base_version)
        holders: set[asyncio.Task[None]] = request.app.state.pool_holders
        for task in tuple(holders):
            task.cancel()
        if holders:
            await asyncio.gather(*holders, return_exceptions=True)
        holders.clear()
        return {"status": "reset", "service": service_settings.service}

    @app.get("/__control/status")
    async def fault_status(
        token: Annotated[str | None, Header(alias="X-Lab-Control-Token")] = None,
    ) -> dict[str, str | None]:
        _authorize_control(token, service_settings)
        active = fault_state.current()
        return {
            "service": service_settings.service,
            "status": "active" if active else "clear",
            "expires_at": active.expires_at.isoformat() if active else None,
        }

    if service_settings.service == "gateway":

        @app.post("/checkout", response_model=LabResult)
        async def gateway_checkout(order: LabOrder, request: Request) -> LabResult:
            _apply_request_cpu_fault(fault_state.current())
            return await _call_dependency(
                request=request,
                order=order,
                dependency="checkout",
                url=f"{service_settings.checkout_url}/checkout",
                metrics=metrics,
                tracer=tracer,
            )

    if service_settings.service == "checkout":

        @app.post("/checkout", response_model=LabResult)
        async def checkout_transaction(order: LabOrder, request: Request) -> LabResult:
            active = fault_state.current()
            _apply_request_cpu_fault(active)
            if active is not None and active.command.kind == "deployment_regression":
                if active.command.delay_ms:
                    await asyncio.sleep(active.command.delay_ms / 1_000)
                if _selected(order.order_id, active.command.seed, active.command.error_rate):
                    raise HTTPException(status_code=500, detail="checkout processing regression")
            await _record_order(request, order, metrics, "processing")
            result = await _call_dependency(
                request=request,
                order=order,
                dependency="payments",
                url=f"{service_settings.payments_url}/pay",
                metrics=metrics,
                tracer=tracer,
            )
            await _record_order(request, order, metrics, "completed")
            active = fault_state.current()
            return LabResult(
                order_id=order.order_id,
                status=result.status,
                service=service_settings.service,
                deployment_version=_current_version(active, base_version),
            )

    if service_settings.service == "payments":

        @app.post("/pay", response_model=LabResult)
        async def pay(order: LabOrder, request: Request) -> LabResult:
            active = fault_state.current()
            _apply_request_cpu_fault(active)
            if active is not None and active.command.kind == "latency":
                await asyncio.sleep(active.command.delay_ms / 1_000)
            if active is not None and active.command.kind == "dependency_errors":
                if _selected(order.order_id, active.command.seed, active.command.error_rate):
                    raise HTTPException(status_code=503, detail="payment processor unavailable")
            redis_client = _redis(request)
            cache_key = f"payment:{order.payment_token}"
            bypass_cache = active is not None and active.command.kind == "cache_degradation"
            cached = None if bypass_cache else await redis_client.get(cache_key)
            if cached is not None:
                metrics.cache.labels(service_settings.service, "hit").inc()
            else:
                metrics.cache.labels(service_settings.service, "miss").inc()
                await _payment_db_lookup(request, metrics)
                if bypass_cache:
                    await asyncio.sleep(0.035)
                else:
                    await redis_client.set(cache_key, "approved", ex=300)
            return LabResult(
                order_id=order.order_id,
                status="approved",
                service=service_settings.service,
                deployment_version=base_version,
            )

    return app


def _authorize_control(token: str | None, settings: LabServiceSettings) -> None:
    if not verify_control_token(token, settings.control_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def _validate_fault_for_service(
    command: FaultCommand,
    settings: LabServiceSettings,
) -> None:
    allowed = {
        "gateway": {"resource_contention", "metrics_disabled"},
        "checkout": {
            "pool_exhaustion",
            "deployment_regression",
            "resource_contention",
            "metrics_disabled",
        },
        "payments": {
            "latency",
            "dependency_errors",
            "cache_degradation",
            "resource_contention",
            "metrics_disabled",
        },
    }
    if command.kind not in allowed[settings.service]:
        raise HTTPException(status_code=422, detail="fault is not allowed for this service")
    if command.hold_connections > settings.db_pool_size:
        raise HTTPException(status_code=422, detail="hold_connections exceeds pool size")


async def _call_dependency(
    *,
    request: Request,
    order: LabOrder,
    dependency: str,
    url: str,
    metrics: LabMetrics,
    tracer: Any,
) -> LabResult:
    started = time.perf_counter()
    headers = {"X-Request-ID": request.state.request_id}
    with tracer.start_as_current_span(
        f"dependency.{dependency}",
        attributes={"server.address": dependency},
    ) as span:
        inject(headers)
        try:
            client: httpx.AsyncClient = request.app.state.http
            response = await client.post(url, json=order.model_dump(), headers=headers)
            outcome = "success" if response.status_code < 500 else "error"
            metrics.outbound.labels(metrics.service, dependency, outcome).inc()
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
                raise HTTPException(
                    status_code=502,
                    detail=f"{dependency} dependency failed",
                )
            return LabResult.model_validate(response.json())
        except httpx.TimeoutException as exc:
            metrics.outbound.labels(metrics.service, dependency, "timeout").inc()
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            raise HTTPException(status_code=504, detail=f"{dependency} timed out") from exc
        except httpx.RequestError as exc:
            metrics.outbound.labels(metrics.service, dependency, "unavailable").inc()
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            raise HTTPException(status_code=503, detail=f"{dependency} unavailable") from exc
        finally:
            metrics.outbound_duration.labels(metrics.service, dependency).observe(
                time.perf_counter() - started
            )


def _pool(request: Request) -> AsyncConnectionPool[AsyncConnection[tuple[Any, ...]]]:
    return cast(
        AsyncConnectionPool[AsyncConnection[tuple[Any, ...]]],
        request.app.state.pool,
    )


def _redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


async def _record_order(
    request: Request,
    order: LabOrder,
    metrics: LabMetrics,
    order_status: str,
) -> None:
    pool = _pool(request)
    started = time.perf_counter()
    try:
        async with pool.connection(
            timeout=request.app.state.settings.db_pool_timeout_seconds
        ) as connection:
            metrics.db_pool_wait.labels(metrics.service).observe(time.perf_counter() - started)
            metrics.db_pool_in_use.labels(metrics.service).inc()
            try:
                await connection.execute(
                    """
                    INSERT INTO lab.orders (order_id, amount_cents, status, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (order_id) DO UPDATE
                    SET status = EXCLUDED.status, updated_at = now()
                    """,
                    (order.order_id, order.amount_cents, order_status),
                )
            finally:
                metrics.db_pool_in_use.labels(metrics.service).dec()
    except PoolTimeout as exc:
        metrics.db_pool_timeouts.labels(metrics.service).inc()
        raise HTTPException(status_code=503, detail="database pool unavailable") from exc


async def _payment_db_lookup(request: Request, metrics: LabMetrics) -> None:
    pool = _pool(request)
    started = time.perf_counter()
    try:
        async with pool.connection(
            timeout=request.app.state.settings.db_pool_timeout_seconds
        ) as connection:
            metrics.db_pool_wait.labels(metrics.service).observe(time.perf_counter() - started)
            metrics.db_pool_in_use.labels(metrics.service).inc()
            try:
                await connection.execute("SELECT count(*) FROM lab.orders")
            finally:
                metrics.db_pool_in_use.labels(metrics.service).dec()
    except PoolTimeout as exc:
        metrics.db_pool_timeouts.labels(metrics.service).inc()
        raise HTTPException(status_code=503, detail="database pool unavailable") from exc


async def _start_pool_holders(
    request: Request,
    active: ActiveFault,
    metrics: LabMetrics,
) -> None:
    pool = _pool(request)
    holders: set[asyncio.Task[None]] = request.app.state.pool_holders

    async def hold() -> None:
        try:
            async with pool.connection(timeout=1):
                metrics.db_pool_in_use.labels(metrics.service).inc()
                try:
                    remaining = max(0, active.expires_monotonic - time.monotonic())
                    await asyncio.sleep(remaining)
                finally:
                    metrics.db_pool_in_use.labels(metrics.service).dec()
        except PoolTimeout:
            metrics.db_pool_timeouts.labels(metrics.service).inc()

    for _ in range(active.command.hold_connections):
        task = asyncio.create_task(hold())
        holders.add(task)
        task.add_done_callback(holders.discard)
    await asyncio.sleep(0.1)


def _selected(order_id: str, seed: int, rate: float) -> bool:
    # Deterministic fault selection is required for replay; this is not a security decision.
    return random.Random(f"{seed}:{order_id}").random() < rate  # noqa: S311


def _apply_request_cpu_fault(active: ActiveFault | None) -> None:
    if active is not None and active.command.kind == "resource_contention":
        bounded_cpu_work(active.command.cpu_ms)


def _current_version(active: ActiveFault | None, base_version: str) -> str:
    if active is not None and active.command.kind == "deployment_regression":
        return active.command.deployment_version or base_version
    return base_version


def main() -> None:
    settings = LabServiceSettings()  # type: ignore[call-arg]
    uvicorn.run(
        create_lab_app(settings),
        host="0.0.0.0",  # noqa: S104 - container-only listener; host publishing stays loopback.
        port=settings.port,
        log_config=None,
    )
