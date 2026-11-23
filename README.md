# Timestamp Validation and Clock-Skew Tolerance in postfiatd

## Verdict

**A validation is current iff its signing time lies in (now − 3 min, now + 5 min) and its seen time is zero or before now + 3 min, judged against the receiver's network-adjusted clock — not raw wall time. Each accepted round re-centres that clock on the lower weighted median of peer close times, applied with quarter-step damping, so a skewed node is pulled toward the network majority rather than rejecting it. The hard limits are the absences: there is no `ledgerMAX_CLOSE`, no NTP/SNTP client, no leap-second or DST handling, no wall-clock bound on a peer proposal's close time, and no wall-clock check on a ledger's own close time at accept — only the 5-minute parent-close-time bound in `canBeCurrent()`. Where xrpl.org docs disagree with the code, this pack follows the code: the close-time resolution defaults to 30 s (not "usually 10 s"), and round consensus is declared at 67% (not the 80% validation-quorum concept).**

## Key numbers (SOURCE-DERIVED from the pinned tree — no live node was run)

- Pinned source: postfiatd `0085a1ff885d6a446369cf73a4430f75af22be55`.
- 43 timestamp rules catalogued (T-01..T-37 VERIFIED, T-38/T-39/T-40 SPECIFIED, T-41 MODELLED, T-42/T-43 UNTESTABLE).
- 8 scripted scenarios, 48 synthetic validators: accepted 36, stale_future 5, stale_past 4, stale_seen 3; 19 laggards, 19 stale proposals; close-time consensus in 3 of 8 scenarios; canBeCurrent 8 pass / 2 fail. (Recomputed by `run-manifest.json` from the simulator output; see `outputs/derived/timestamp-results.json`.)
- `isCurrent()` predicate — `signTime > now - CURRENT_EARLY && signTime < now + CURRENT_WALL && (seenTime == 0 || seenTime < now + CURRENT_LOCAL)` (`src/xrpld/consensus/Validations.h:162-165`).
- Validation windows: CURRENT_WALL 5 min, CURRENT_LOCAL 3 min, CURRENT_EARLY 3 min, SET_EXPIRES 10 min, FRESHNESS 20 s (`src/xrpld/consensus/Validations.h:50-89`).
- Close time: `closeTime() = now() + closeOffset_` (`src/xrpld/core/TimeKeeper.h:69-86`); adjustment damped to one quarter of the measured offset (`:88-116`).
- Close-time resolutions 10/20/30/60/90/120 s, default 30 s (`src/xrpld/consensus/LedgerTiming.h:35-47`); close-time consensus needs 75% of participants (`src/xrpld/consensus/Consensus.h:1507-1641`).
- Median close offset re-centres the clock each accepted round (`src/xrpld/app/consensus/RCLConsensus.cpp:704-728`).
- `canBeCurrent()`: parent close time within 5 min of our clock (`src/xrpld/app/ledger/detail/LedgerMaster.cpp:364-398`).
- Consensus declaration: minimum 1.95 s, maximum 15 s, 67% agreement, abandon at 120 s (`src/xrpld/consensus/Consensus.cpp:176-270`).
- No `ledgerMAX_CLOSE` (0 grep hits); the `ConsensusParms` validation windows are dead copies (0 references outside their definitions).
- Probe: 12/12 checks PASS (rule anchors, `isCurrent()` re-grep, key tokens at recorded lines, median + damping re-grep, count reconciliation, determinism, excerpt + blob integrity, absence re-greps, 67%/30 s checks, timing sanity).
- Excerpts: 52 verbatim pinned-source excerpts, 21 source files, blob SHAs + sizes re-checked against the checkout.

## Counts

- Findings: 12 (HIGH 3, MEDIUM 5, LOW 4).
- Claims: 24 (VERIFIED 16, SPECIFIED 2, MODELLED 4, UNTESTABLE 2).
- Risks: 14 (HIGH 3, MEDIUM 8, LOW 3).
- Gaps: 8.

## Boundary

No live node was run and no validation was submitted. The simulator models the cited rules on scripted, synthetic skew loads; every scenario outcome is a model output, not an observed network result. Live convergence of the close-offset feedback loop (T-42) and the live close interval/resolution actually observed (T-43) are UNTESTABLE from source alone. The `seen == sign` modelling choice (validations evaluated as authored, before any peer re-stamp of the seen time) is stated in `docs/methodology.md`. Simulated/modelled material is separated from directly-observed source facts in `docs/methodology.md`.

## Reproduce

```bash
python3 src/timestamp_model.py               # simulator -> outputs/derived/timestamp-results.json + scenario-matrix.json
python3 scripts/probe.py                    # 12 probe checks, exit 0 only if all pass
python3 scripts/extract_excerpts.py         # verbatim pinned-source excerpts + hashes
bash scripts/run_all.sh                     # full suite end to end
bash scripts/clean_reproduce.sh             # full fresh-environment check
bash scripts/verify_digests.sh              # sha256sum -c SHA256SUMS
```

Only deterministic source parsing and simulation runs. No live node, no submitted validations, no votes, no live key material, no credentials anywhere in the pack.

## CI run

CI workflow runs page: https://github.com/araupooo/postfiatd-timestamp-validation-clock-skew/actions/workflows/verify.yml

Specific CI run URL: https://github.com/araupooo/postfiatd-timestamp-validation-clock-skew/actions/runs/45255904318 (verify workflow, completed success on HEAD 7e9494915503ad97bf17a34d7a2d1508cf9b48b6).

## Fresh-clone reproduction log

Fresh-clone repro log SHA-256: 39f6082b9334b5211852b25d463f56e707e2de0843239ba4b52925d5114b5b01 (the log is `outputs/fresh-clone-run.log`).

## File map

- `README.md` — this file.
- `findings.json` — 12 findings with severity, status, evidence.
- `run-manifest.json` — pinned commit, counts recomputed from the tables.
- `docs/` — decision memo, scenario matrix, methodology, claim-to-evidence index, excerpts, citations, evidence index, risk register, gap register.
- `src/timestamp_model.py` — stdlib-only deterministic timestamp simulator (rules T-01..T-37).
- `scripts/` — simulator runner, probe, excerpts, reproduce, compare, digests.
- `configs/timestamp-rules.json` — the 43-rule catalog; `configs/scenarios.json` — the 8 scripted scenarios.
- `fixtures/source-excerpts/` — 52 verbatim pinned-source excerpts with file paths and grep-verified line numbers.
- `fixtures/source-hashes.json` — SHA-256 digests and git blob SHAs for every cited source file.
- `outputs/` — unedited simulator/probe logs, derived JSONs, fresh-clone reproduction evidence.
- `SHA256SUMS` — digests of every pack file except itself, the internal-only `PACK-READY.md`, and the internal-only `research/` directory.
