# Methodology

## Pinned source

postfiatd commit `0085a1ff885d6a446369cf73a4430f75af22be55` (repo `postfiatorg/postfiatd`). A local checkout at `~/workspace/postfiatd-pin-0085a1f` was verified with `git rev-parse HEAD` before any excerpt was taken. Every line number in this pack was verified with `grep -n` on that checkout; no line number was taken from a web fetch. `scripts/extract_excerpts.py` re-derives all 52 excerpts from the checkout and records SHA-256 digests plus git blob SHAs in `fixtures/source-hashes.json` (21 source files); `scripts/probe.py` re-checks every manifest blob SHA and size against `git hash-object` and the checkout file size.

## Where the code wins over the docs

- **Close-time resolution defaults to 30 s, not "usually 10 s".** `LedgerTiming.h:44` sets `ledgerDefaultTimeResolution = ledgerPossibleTimeResolutions[2]` = 30 s; 10 s is only the genesis resolution (`:47`) and the finest bin (`:36`). xrpl.org's "usually 10" describes steady-state live behaviour; the pack follows the code and reconciles the two through the adaptation mechanism (T-21).
- **The quorum is 67% for round consensus, not 80%.** `ConsensusParms.h:79` sets `minCONSENSUS_PCT = 67`; the 80% figure on xrpl.org is the *validation* quorum concept, not the round-declaration threshold.
- **`docs/consensus.md` threshold naming is stale.** The doc cites `AV_XXX_CONSENSUS_PCT` / `AV_XXX_CONSENSUS_TIME`; the code has no `AV_*` constants — the table is `avalancheCutoffs` with `{time, percent, next}` triples (`ConsensusParms.h:146-157`).
- **The `validationCURRENT_WALL` comment is loose.** It says "after its ledger's close time"; the enforced predicate compares `signTime` against local `now` (T-10). The pack quotes the predicate, not the comment, as the rule.

## Simulator model (`src/timestamp_model.py`, stdlib only, deterministic)

The engine implements rules T-01..T-37 in pipeline order: (0) receiver clock = base + receiver skew + close offset (T-02/T-03/T-17); (1) `isCurrent()` three-clause check with the three failure modes reported separately (T-10); (2) laggard check, `now >= seen + 20 s` (T-16); (3) proposal staleness, `seen <= now - 20 s` (T-30); (4) close-time vote: proposals rounded with `roundCloseTime()` at the scenario resolution, tallied, adopted at `participantsNeeded(n, 50)`, consensus at `participantsNeeded(n, 75)` with `participantsNeeded(n, pct) = max(1, (n*pct + pct/2)//100)` integer arithmetic, bins walked highest-time first so tied bins resolve to the earliest (T-24); (5) effective close time / agree-to-disagree fallback, prior close + 1 s with `closeFlags = sLCF_NoConsensusTime` (T-23/T-25); (6) lower weighted median offset applied with quarter-step damping (T-26/T-04), reproducing C++ integer division truncating toward zero; (7) resolution adaptation, coarser after a missed agreement, finer after agreement every 8 ledgers (T-21); (8) `canBeCurrent()` 5-minute parent-close bound (T-33). No wall-clock bound is applied to peer proposals or to a ledger's own close time, because the code has none.

Scenario parameters that the code cannot supply are labelled as parameters, not derived values: the base time (a fixed synthetic Ripple-epoch second, 800000000), the validator skews, the resolutions, and the drift traces are scenario inputs (T-42/T-43: live values are unknowable from source alone).

## Modelling choices the reader must know

- **Seen time is modelled as authored (`seen == sign`, T-19).** The simulator evaluates `isCurrent()` on each validation as its author created it, where `seenTime_ = signTime`. That is the strictest reading: it is why S-01's +299 s validator is `stale_seen` and S-03's +180 s validator is `stale_seen` — their signing times are inside the window but their seen times are not. A copy relayed by a peer is re-stamped by `PeerImp` to the receiver's `closeTime()` (T-12), which can only make the seen clause easier to pass; the pack does not model the relayed case as a separate pass, and says so here rather than silently assuming one stamping or the other.
- **Laggard/proposal-stale outputs are single-snapshot evaluations.** A validator whose last validation was seen 30 s ago counts as a laggard (T-16) in that snapshot; a validator signing every round would be re-seen and would not stay a laggard. The simulator does not invent re-signing.
- **The S-07 +10 s single-round median is a resolution-grid rounding artifact.** All peers report the same close time (base), which rounds to base + 10 s at 30 s resolution because base % 30 = 20; the drift trace, not the single-round median, is S-07's headline result.
- **S-07/S-08 multi-round traces are MODELLED replays.** The measured offsets per round are scenario inputs; only the quarter-step application (T-04) and the UNL bow-out comparison (T-36) are code rules.

## What is simulated, specified, or directly observed

- **DIRECTLY OBSERVED (source-derived)** — rules T-01..T-37: each carries a cited file range and an anchor re-verified inside that range by `scripts/probe.py` (A-01), plus token-level checks (D-01), the `isCurrent()` re-grep (C-01), the median/damping re-grep (E-01), the absence re-greps (I-01), and the 67%/30 s checks (J-01). Absence findings (no `ledgerMAX_CLOSE`, no NTP, no leap-second/DST handling, no wall-clock bounds, no skew alerting) are 0-hit grep results, re-run by the probe — they are observations of the tree, not inferences.
- **SPECIFIED** — T-38/T-39 (xrpl.org ledger-structure and consensus-protocol pages, URL + section); T-40 (in-tree `docs/consensus.md`, not code). The 80% and "usually 10 s" figures are doc statements, not pinned-code facts.
- **SIMULATED / MODELLED** — every scenario outcome; T-41 (the implied ±5 min / −3 min tolerance window); the S-07 drift trace and UNL bow-out replay; the S-08 leap-second dead-band inference, malicious-proposal vote, and rejoin pull-back trace; the batch form of nothing here — no batch approximation is used. The simulator is a model of the cited rules, not a run of postfiatd: no live node was run, no validation was submitted, no consensus round was observed.
- **UNTESTABLE in this pack** — live convergence rate of the offset feedback loop (T-42); live close interval / resolution observed (T-43); the deployed network's quorum choice (67% vs 80%) as a deployment fact.

## Determinism

Re-runs produce byte-identical outputs: sorted keys and rows, no timestamps, no absolute paths, no elapsed times in any deterministic output. Timing is sanity-checked (non-negative) in `probe.py` and never recorded. `scripts/compare_reproduce.py` deep-compares a fresh run against the shipped outputs ignoring only volatile fields.
