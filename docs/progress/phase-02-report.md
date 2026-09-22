# PHASE 2 REPORT — Lab Telemetry and Incident Captures

Status: PASS

Date: 2026-09-22

## 1. Objective and result

Phase 2 implemented and exercised a real, bounded local transaction laboratory. Separate `gateway`, `checkout`, and `payments` HTTP processes now execute fabricated checkout traffic through an isolated PostgreSQL database and Redis cache. Prometheus scrapes actual service metrics, each request emits bounded structured logs, and W3C trace context propagates across all three services.

The gate passes. Six controlled fault families were observed through real requests and telemetry. The final committed set contains exactly two independently executed live captures for each required fault family plus five separate control captures. Every capture has a cutoff, workload summary, metrics, logs, traces, topology, changes, recovery result, and SHA-256 manifest. The executable verifier confirms the required signals, cross-service trace continuity, successful recovery, capture hashes, and separation of evaluator-only labels.

All faults remained inside the loopback/container lab, were capped at 30 seconds, and were reset before the next run. No dataset was downloaded: Phase 2 produced a small 2.9 MiB laboratory dataset from independently executed local workloads. No model, embedding, paid API, GPU, or Colab run was used.

## 2. Implemented changes

- One shared, non-root lab image runs three distinct FastAPI service processes.
- `gateway` accepts fabricated orders and calls `checkout`.
- `checkout` persists order state in the isolated lab PostgreSQL and calls `payments`.
- `payments` performs deterministic sandbox approval, uses Redis, and exercises lab PostgreSQL on cache misses.
- Bounded workload generation enforces duration, request-rate, concurrency, and total-request caps.
- Operator-only fault endpoints require a separate hashed-comparison token, are loopback-published, and auto-expire.
- Prometheus records bounded request, dependency, pool, cache, deployment, and process metrics.
- JSON logs include timestamps, severity, service, environment, request ID, route template, deployment version, safe status fields, trace ID, and span ID.
- OpenTelemetry SDK spans are exported to bounded local JSONL files and use propagated W3C trace headers.
- Capture tooling uses fixed server-owned PromQL templates with explicit range, cutoff, and one-second step.
- Capture verification checks hashes, labels, telemetry effects, trace continuity, recovery, and evaluator-data isolation.
- Redis 8.10.1, Prometheus 3.14.0, Python 3.12.14, and uv 0.12.17 images are pinned by tested ARM64 digest.

## 3. Fault and control implementation

| Scenario | Bounded mechanism | Required observed evidence |
|---|---|---|
| Downstream latency | Up to 500 ms delay in payments; suite uses 220 ms | Payments dependency p95, propagated caller latency |
| Pool exhaustion | At most four held checkout pool connections | Pool occupancy, acquisition timeouts, failed requests |
| Dependency errors | Deterministic seeded payments error fraction, capped at 0.9 | Payments errors and propagated gateway failures |
| Cache degradation | Bypass cache and perform PostgreSQL lookup with bounded delay | Miss rate, database use, higher latency |
| Deployment regression | Explicit checkout version plus seeded delay/error behavior | Deployment series/change record, later errors/latency |
| Resource contention | At most 200 ms bounded CPU work per request; suite uses 90 ms | Process CPU rate and request latency |

The additional controls are healthy traffic, healthy high traffic, a low-CPU correlated distractor with the true failure downstream, incomplete payments metrics, and a two-cause checkout-deployment/payments-latency case.

## 4. Capture evidence

The final eligible capture set contains 17 independent runs:

| Scenario | Captures | Failures across runs | Observed workload p95 |
|---|---:|---:|---:|
| Downstream latency | 2 | 0 | 252.505–255.704 ms |
| Pool exhaustion | 2 | 60 | 270.633–272.016 ms |
| Dependency errors | 2 | 33 | 24.295–25.370 ms |
| Cache degradation | 2 | 0 | 71.282–74.237 ms |
| Deployment regression | 2 | 19 | 120.825–124.148 ms |
| Resource contention | 2 | 0 | 99.663–123.082 ms |
| Healthy | 1 | 0 | 25.435 ms |
| Healthy high traffic | 1 | 0 | 16.327 ms |
| Misleading correlation | 1 | 20 | 30.428 ms |
| Incomplete telemetry | 1 | 0 | 27.891 ms |
| Ambiguous two-cause | 1 | 4 | 237.623 ms |

Representative Prometheus observations from the eligible suite:

- Payments dependency p95 reached 0.2425 seconds during downstream latency.
- Checkout pool occupancy reached exactly its configured size of 4, with a bounded timeout increase during exhaustion.
- Payments dependency error rate reached 3.25 requests/second in a sampled error capture.
- Cache-miss rate reached 6 requests/second during cache degradation.
- `checkout` version `v1.1.0-regressed` was observable with gauge value 1 and a corresponding change record.
- Payments process CPU rate reached approximately 0.535 CPU-seconds/second during resource contention.
- Payments scrape health reached 0 during the incomplete-telemetry capture; it was not interpreted as healthy or zero-valued data.

These numbers describe bounded laboratory runs only. They are not capacity, production reliability, or causal-model performance claims.

## 5. Verification evidence

| Check | Result | Evidence |
|---|---|---|
| Static checks | PASS | Ruff passed; strict mypy passed 14 source files |
| Unit checks | PASS | 15 passed |
| Durable queue integration | PASS | 1 real PostgreSQL recovery test passed |
| Live lab integration | PASS | Real transaction/Prometheus/control-boundary test plus capture contract test passed |
| Capture count | PASS | 12 independent required-fault captures plus 5 controls |
| Fault effects | PASS | All 17 evaluator records have measured effect checks appropriate to their scenario |
| Recovery | PASS | Every capture's post-reset probe completed all requests successfully |
| Prometheus targets | PASS | gateway, checkout, and payments all report `up` after the suite |
| Trace propagation | PASS | At least one request per capture retains one trace ID across every reached dependency |
| Hash integrity | PASS | All 17 SHA-256 manifests validate |
| Evaluator separation | PASS | No forbidden label field appears in snapshots; evaluator data is absent from runtime image |
| Secret scan | PASS | Four configured password/token values scanned; none occurs in capture artifacts |
| Fault cleanup | PASS | All three service control states report `clear` after the suite |

`make verify-captures` produced:

```text
capture_count: 17
independent_fault_capture_count: 12
control_capture_count: 5
hash_manifests_valid: true
telemetry_signals_valid: true
trace_continuity_valid: true
evaluator_separation_valid: true
recovery_valid: true
```

## 6. Resource measurement

The configured normal profile remains below the approximately 8 GiB target. A post-suite idle sample used approximately 920 MiB across all eight containers:

| Service | Observed memory / limit |
|---|---:|
| Application PostgreSQL | 26.35 MiB / 768 MiB |
| Lab PostgreSQL | 35.96 MiB / 512 MiB |
| Neo4j | 595.3 MiB / 1.5 GiB |
| Redis | 11.6 MiB / 128 MiB |
| Prometheus | 46.8 MiB / 512 MiB |
| gateway | 67.65 MiB / 256 MiB |
| checkout | 68.53 MiB / 256 MiB |
| payments | 67.78 MiB / 256 MiB |

This is one idle sample after faults cleared, not a load or capacity benchmark.

## 7. Rejected intermediate captures

The first instrumentation pass counted database waiters in a gauge named `in_use`, which allowed a value of 5 for a pool configured with 4 connections. The fault itself was real, but that metric did not precisely match its contract. Those uncommitted captures were moved intact to `data/runtime/rejected-phase2-telemetry-v1`, which is ignored by Git. The gauge was corrected to increment only after acquisition, the verifier was tightened to require exactly 4 during pool exhaustion, the lab image was rebuilt, and the full suite was rerun. Only the corrected 17 captures are eligible and committed.

## 8. Safety and trust boundaries

- All host ports bind to `127.0.0.1`; inter-service traffic stays on the Compose network.
- Fault endpoints require a separate operator token and are not part of future agent tools.
- Containers do not receive the Docker socket, host shell, production credentials, customer data, or evaluator directory.
- The shared image runs as UID 10001.
- Fault duration, delay, CPU work, error fraction, held connections, workload concurrency, rate, duration, and request count all have hard bounds.
- Every scenario resets controls and runs a healthy recovery probe.
- Prometheus labels use bounded service/route/status/dependency values; request IDs remain in logs/traces.

## 9. Coverage and limitations

The retained global `make coverage` threshold remains 85 percent and currently fails at 32.69 percent after adding the process-heavy lab implementation. The threshold was not lowered. Phase 2 is accepted through unit checks, real integration tests, and executable capture verification; the specification's 85 percent target applies to the later core domain, policy, retrieval, and orchestration code and remains unmet.

Other limitations:

- This is laboratory data, not production incident evidence.
- Phase 2 captures predate the curated Phase 3 corpus. They can validate telemetry and faults but must be recaptured after corpus versioning before any final as-of benchmark pairing.
- Traces use a small local JSONL exporter rather than a full trace backend.
- The current API still does not run an investigator or diagnose these captures.
- Process CPU is container-process evidence, not host or VM CPU.

## 10. How to try it

```bash
make lab-up
make scenario SCENARIO=downstream_latency
make verify-captures
make test-lab-integration
```

Normal teardown remains `make down`, which preserves named database and Prometheus volumes. Runtime logs are bounded and ignored by Git. Capture artifacts are small, hashed, and committed separately from evaluator labels.

## 11. Next phase

Phase 3 will add Neo4j graph constraints, authoritative topology ingestion, a curated versioned corpus, bounded chunking/embeddings, full-text/vector indexes, temporal eligibility, and idempotent ingestion reports. It must not begin until the user approves Phase 3.

No Colab run is currently required. Local embedding suitability will be measured in Phase 3 before any larger download or heavy operation.

## 12. Resume state

- Phase 2 status: PASS.
- Runtime: all eight containers are running; the three Prometheus targets are up; all fault states are clear.
- Eligible data: 17 captures, 153 files, approximately 2.9 MiB.
- Evaluator labels: `data/evaluator/phase2-labels.jsonl`, never mounted into runtime.
- Rejected local audit set: retained under ignored `data/runtime/rejected-phase2-telemetry-v1`.
- Exact next action: wait for explicit Phase 3 approval, then define the graph schema and corpus manifest before downloading an embedding model.
