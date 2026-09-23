from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Literal

from incidentgraph.ingestion import ServiceRecord, TopologyRecord
from incidentgraph.models import DependencyEdge, DependencyView, EventRecord, ServiceSummary


class RateLimitExceeded(RuntimeError):
    pass


class LocalRateLimiter:
    """Bound local API abuse without pretending to be a distributed gateway."""

    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, principal_id: str) -> None:
        now = time.monotonic()
        cutoff = now - 60
        with self._lock:
            requests = self._requests[principal_id]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                raise RateLimitExceeded("local API rate limit exceeded")
            requests.append(now)


def _service(item: ServiceRecord) -> ServiceSummary:
    return ServiceSummary(
        service_id=item.id,
        name=item.name,
        aliases=list(item.aliases),
        environment=item.environment,
        owner=item.owner,
        metadata_version=item.metadata_version,
    )


def authorized_services(
    topology: TopologyRecord,
    service_ids: frozenset[str],
) -> list[ServiceSummary]:
    return [_service(item) for item in topology.services if item.id in service_ids]


def dependency_view(
    topology: TopologyRecord,
    *,
    service_id: str,
    authorized_service_ids: frozenset[str],
    cutoff: datetime,
    direction: Literal["inbound", "outbound", "both"],
    depth: int,
) -> DependencyView | None:
    cutoff = cutoff.astimezone(UTC)
    if service_id not in authorized_service_ids:
        return None
    if cutoff < topology.valid_from.astimezone(UTC):
        return None
    if topology.valid_to is not None and cutoff >= topology.valid_to.astimezone(UTC):
        return None
    eligible_edges = [
        edge
        for edge in topology.dependencies
        if edge.caller in authorized_service_ids and edge.callee in authorized_service_ids
    ]
    visited = {service_id}
    frontier = {service_id}
    selected: set[tuple[str, str]] = set()
    for _ in range(depth):
        next_frontier: set[str] = set()
        for edge in eligible_edges:
            outbound = direction in {"outbound", "both"} and edge.caller in frontier
            inbound = direction in {"inbound", "both"} and edge.callee in frontier
            if outbound:
                selected.add((edge.caller, edge.callee))
                next_frontier.add(edge.callee)
            if inbound:
                selected.add((edge.caller, edge.callee))
                next_frontier.add(edge.caller)
        next_frontier -= visited
        visited |= next_frontier
        frontier = next_frontier
        if not frontier:
            break
    services = [_service(item) for item in topology.services if item.id in visited]
    services.sort(key=lambda item: item.service_id)
    edges = [DependencyEdge(caller=caller, callee=callee) for caller, callee in sorted(selected)]
    return DependencyView(
        service_id=service_id,
        cutoff=cutoff,
        direction=direction,
        depth=depth,
        services=services,
        edges=edges,
    )


def encode_sse(event: EventRecord) -> bytes:
    payload = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
    return f"id: {event.sequence}\nevent: {event.kind}\ndata: {payload}\n\n".encode()
