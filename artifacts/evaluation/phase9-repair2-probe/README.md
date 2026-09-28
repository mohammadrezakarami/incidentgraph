# Phase 9 repair-2 development probe

This directory preserves the returned free-Colab development replay as failure-analysis evidence.
The uploaded archive had SHA-256
`6b82caa667b49351e6595291ccd36ebe8cc2bbe44b43ad78f06f540777dae86b`.

The run produced 10 structurally valid reports in 11 model calls, with one rejected first attempt
and 7/10 eventual label matches. First-pass label match was 6/10. The three final errors were:

- `incident-v3-dev-007`: wrongly abstained from a single payments dependency-error signal.
- `incident-v3-dev-019`: wrongly abstained from the same bounded mechanism in the misleading-
  correlation scenario.
- `incident-v3-dev-021`: wrongly abstained from complete healthy telemetry and described zero
  error rates as observed errors.

The accepted outputs also exposed semantic defects that structural validation did not catch:
free-form rationales could misdescribe cited facts, and several rationales ended at the schema's
240-character limit. This archive is therefore a failed diagnosis-quality probe, not authorization
for held-out evaluation and not a Phase 9 pass.

File hashes:

- `records.json`: `ec6cde6c6f29beee26eefddd827e6b817f9861907371d17fe2b9f2fa3eb0f838`
- `summary.json`: `7b296c6c3b85ff6c937c67f10990409c0f584128bf989597a68ca5310ee9ff20`
