# Phase 8 Security Verification Map

Last verified: 2026-09-23

| Boundary | Executable evidence | Expected result |
|---|---|---|
| Bearer and DSN redaction | `tests/unit/test_observability.py` | Nested keys, bearer strings, assignments, and URI credentials are removed before export |
| Trace-secret sampling | `tests/integration/test_phase8_hardening.py` | The API token and authorization field are absent from the correlated trace records |
| Prompt/corpus injection | `tests/unit/test_security.py` | An added shell argument is schema-invalid and an unauthorized service remains forbidden |
| Read-only dependency outage | `tests/unit/test_security.py` and Phase 8 integration | The adapter returns a typed error and does not leak the source exception text |
| Cross-user/API scope | `tests/integration/test_phase7_api.py` | Unauthorized reads and mutations fail without revealing another owner's record |
| Malicious request bounds | `tests/unit/test_api.py`, `tests/unit/test_investigator.py` | Body, rate, time, service, tool, duplicate-call, and budget constraints remain enforced |
| Durable stale execution | `tests/integration/test_durable_queue.py` | Expired/stale attempts cannot publish or duplicate a review effect |
| Event retention | `tests/integration/test_phase8_hardening.py` | Preview and scoped deletion affect only rows older than the configured boundary |

These tests demonstrate the named controls for the tested local design. They do not establish
general prompt-injection immunity, public Internet safety, compliance, or production-grade
multi-tenancy.
