# Technical defense guide

These are concise interview answers. Lead with the decision, then its tradeoff and evidence. Do not
turn laboratory measurements into production claims.

## 1. Why an adaptive agent instead of only fixed retrieval?

A fixed retrieval plan is efficient when the required evidence is known, so IncidentGraph retains
one as a baseline. Incident investigation is conditional: a latency series may make downstream
metrics useful, while a deployment event may make change history the next best observation. The
agent selects among registered observations after each result. Deterministic policy still owns
authorization, time scope, budgets, and tool arguments, so adaptivity does not mean arbitrary
execution. V4 also showed that fixed and adaptive workflows can tie on this small synthetic policy;
the project does not claim the agent always wins.

## 2. How are LangChain and LangGraph used differently?

LangChain provides the OpenAI-compatible chat integration, typed tool schemas, and structured output
parsing at model boundaries. LangGraph provides the long-lived state machine: named nodes,
conditional routes, bounded loops, PostgreSQL checkpoints, and the human-review interrupt/resume.
LangChain answers “how do I call and validate the model/tool contract?”; LangGraph answers “what
stateful step runs next and how can it recover?”

## 3. What does Neo4j add beyond vector similarity?

Vector search asks which chunks are semantically similar inside the authorized target scope. Neo4j
adds reviewed, directional, time-valid operational relationships, allowing bounded expansion from
gateway to checkout to payments before ranking. It also records the exact nodes and relationship
provenance that admitted a downstream document. On the sealed retrieval holdout, graph Recall@5
was 0.925 versus vector 0.8833, although vector had higher MRR@5; graph is not universally better.

## 4. Why one investigator rather than multiple agents?

One investigator keeps identity, evidence, budgets, contradictions, checkpoints, and review state
in one auditable lifecycle. The task does not require competing personas, and multi-agent handoffs
would add token cost, failure modes, attribution ambiguity, and more recovery semantics. Parallel or
specialized agents remain an extension only if measured evidence shows one bounded investigator is
the bottleneck.

## 5. How is evidence obtained, versioned, and cited?

Eight registered tools read reviewed service context, dependencies, bounded metric templates,
redacted logs, approved changes, eligible runbooks, and reviewed incidents. Each evidence record
stores stable identity, source/version, service scope, timestamps, hash, validity, limitations,
snapshot/corpus ID, safe parameters, and provenance. Large raw payloads stay outside checkpoints.
Reports refer to evidence UUIDs, and deterministic validation rejects unknown or unsupported
citations before publication.

## 6. Why do graph relationships and correlated metrics not prove causality?

A dependency edge proves reviewed operational adjacency at a time; metric correlation proves only
that measurements moved together in a window. Neither excludes a common cause, instrumentation
error, or unrelated change. The report therefore distinguishes observations, hypotheses, potential
impact, contradictions, and missing evidence. V4's synthetic-lab policy can identify known injected
mechanisms because the laboratory contract is pre-registered; that must not be generalized to real
production causality.

## 7. How does checkpoint recovery differ from queue delivery and exactly-once effects?

The PostgreSQL queue decides which worker may attempt a task through a lease, token, expiry, and
generation. The LangGraph checkpoint stores the workflow position and bounded state for that
thread. Either can survive a process restart, but they solve different problems. Delivery is
at-least-once; exact-once execution is not claimed. Fencing and stable idempotency keys instead make
report publication, review effects, and lifecycle events safe under retries.

## 8. What does human review authorize?

It authorizes the diagnosis lifecycle for one immutable report version: accept, reject, or request
revision. The decision is bound to identity, role, version, expiry, and idempotency key, then stored
before a new resume task is queued. It does not authorize shell commands, infrastructure changes,
fault injection, deployment, or execution of recommendations because those tools do not exist.

## 9. How is prompt injection constrained outside the prompt?

Model output crosses typed schemas into a fixed tool registry. The server injects the principal and
authorized service IDs, validates environment/window/cutoff, uses reviewed query templates, rejects
duplicate requests, caps rows/nodes/tokens/calls/time/cost, and redacts before storage/export. Tests
show injected shell-like fields and scope expansion fail closed. A prompt is guidance; the policy
boundary is code.

## 10. How is evaluation leakage prevented, and what remains uncertain?

Evaluator labels are stored outside agent-readable captures and excluded from runtime images.
Development and held-out groups are disjoint, label payloads are SHA-256 sealed before result
opening, and prompts/code/model settings/targets are frozen. Failed v1 and v3 results remain
immutable; v4 used a newly sealed post-repair set. Generalization remains uncertain because all data
is project-authored, 30 variants share 11 captures, and the written review is AI-assisted.

## 11. Which baseline won, under what conditions, and at what cost?

For sealed retrieval, graph had the best Recall@5 (0.925), vector the best MRR@5 (0.950), and hybrid
the lowest mean elapsed time (134.469 ms) on a 37-chunk laboratory corpus. For v4 diagnosis, fixed
and adaptive both achieved 20/20 Top-1 and Top-3; fixed was faster because it made zero model calls,
while adaptive made one local model call per held-out case to order observations. Both estimated
paid cost at USD 0. The honest conclusion is conditional tradeoffs, not adaptive dominance.

## 12. What must change before connecting a real organization?

Add enterprise identity and centralized authorization; map approved telemetry sources through a
read-only service account; perform privacy, threat-model, retention, and legal review; build a
representative independently labeled dataset; validate provider/data residency and cost controls;
run sustained load, chaos, recovery, and security assessments; establish monitoring and incident
ownership; and begin with a staged read-only pilot. Automatic remediation would require a separate
risk model, approvals, rollback proof, and explicit authorization—it is not a small configuration
change.

## Short failure story to tell

V1 failed visibly: the fixed prompt overflowed a 4,096-token context, the adaptive workflow used
invalid tool shapes, and factual support was only 32/57. V3 used fresh data but still generated
uncited generic conclusions. The repair did not relabel old results. V4 created a new sealed set,
narrowed the model to observation ordering, and moved the known synthetic-lab decision into trusted
policy code with exact evidence reduction. This improved reliability while also narrowing the claim
from “autonomous diagnosis” to “bounded agent plus trusted laboratory policy.”

## One-sentence positioning

IncidentGraph is a personal, production-inspired local system that demonstrates bounded agent
orchestration, operational GraphRAG, durable review, and evidence-backed evaluation; it is not a
production deployment or proof of real-company business impact.
