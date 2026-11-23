# Evidence index

- `configs/timestamp-rules.json` — 43 rules (T-01..T-37 VERIFIED, T-38/T-39/T-40 SPECIFIED, T-41 MODELLED, T-42/T-43 UNTESTABLE).
- `configs/scenarios.json` — 8 scripted scenarios, 48 synthetic validators.
- `src/timestamp_model.py` — the deterministic timestamp / clock-skew simulator.
- `outputs/derived/timestamp-results.json` — per-scenario outcomes and totals.
- `outputs/derived/scenario-matrix.json` — per-scenario count table.
- `outputs/derived/probe-results.json` — 12 probe checks, all PASS.
- `outputs/run.log`, `outputs/probe-run.log` — unedited run logs.
- `fixtures/source-excerpts/` — 52 verbatim excerpts; `fixtures/source-hashes.json` — digests + blob SHAs.
- `findings.json` — 12 findings.
- `run-manifest.json` — counts recomputed from the tables, plus result/matrix digests.
