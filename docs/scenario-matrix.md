# Scenario matrix

Scripted, synthetic clock-skew loads (model inputs, not observed network traffic). Base time is a fixed synthetic Ripple-epoch second (800000000); every validator skew is an offset from it. Each scenario is run by `src/timestamp_model.py`; per-scenario outcomes live in `outputs/derived/timestamp-results.json` and the count table in `outputs/derived/scenario-matrix.json`.

| ID | Title | Validators | Question |
| --- | --- | --- | --- |
| S-01 | Clock ahead by seconds | 6 | Is a validator whose clock runs seconds fast still accepted, and how far ahead can it run before isCurrent() drops it as stale? |
| S-02 | Clock behind by minutes | 6 | Where exactly does a slow clock stop being accepted — at the -180 s CURRENT_EARLY edge, and what happens one second past it? |
| S-03 | Clock ahead by minutes | 6 | Is a validator whose clock runs minutes fast dropped as stale, and is the +300 s CURRENT_WALL edge strict (signTime == now + 300 s)? |
| S-04 | Close-time drift across a consensus round | 7 | When six of seven peers report a close time 30 s behind ours, does the rounded vote reach 75% close-time consensus, and how far does the median offset pull our adjusted clock in one round? |
| S-05 | Validation expiry under skew | 5 | Does a validation signed 170 s in the past stay current, for how many more seconds, and which validators count as laggards (unseen for 20 s) right now? |
| S-06 | Ledger close-time disagreement and avalanche effects | 8 | When peers split evenly between two close-time bins, does close-time consensus fail, does the round fall back to prior close + 1 s with the NoConsensusTime flag, and does the resolution coarsen? |
| S-07 | NTP loss and free-running clocks | 3 | With no NTP and a wall clock drifting +12 s per round, how does the quarter-step median adjustment pull the adjusted clock back, and does the node bow out when its UNL expires? |
| S-08 | Leap-second and DST edge cases, malicious validator, rejoin after prolonged clock error | 7 | Does a 1 s leap-second step stay inside the adjustment dead band, does DST matter at all (UTC seconds), can a malicious validator's far-future close time win the vote, and how fast does a node returning with a -400 s clock error get pulled back? |

Counts: 8 scenarios, 48 validators.

## Per-scenario outcomes (from the simulator run)

- S-01 clock ahead by seconds: 5 accepted, 1 stale_seen (V-E at +299 s: its signing time is inside the +300 s window but its seen time, equal to its signing time as authored, is not inside the +180 s seen window). No laggards. Close-time consensus FAILS (votes spread 1-1-1-1-1-2 across six bins; 5 needed for 75% of 7 participants). Median offset +70 s, close offset moves 0 → +18 s, resolution coarsens 30 → 60 s, effective close falls back to prior close + 1 s (offset -4 s).
- S-02 clock behind by minutes: 2 accepted (-30 s, -179 s), 4 stale_past (-180 s, -181 s, -240 s, -600 s). The -180 s edge is strict: signTime == now - 180 s is stale. All 6 count as laggards (seen more than 20 s ago). Close-time consensus FAILS; median offset -170 s, close offset moves 0 → -43 s, resolution coarsens 30 → 60 s.
- S-03 clock ahead by minutes: 1 accepted (0 s), 4 stale_future (+300 s, +301 s, +420 s, +600 s), 1 stale_seen (+180 s: signing time inside the window, seen time exactly at now + 180 s, which fails the strict seen clause). The +300 s edge is strict: signTime == now + 300 s is stale. Close-time consensus FAILS; median offset +310 s, close offset moves 0 → +78 s, resolution coarsens 30 → 60 s.
- S-04 close-time drift: 7 accepted, 6 laggards (the six -30 s validators were last seen 30 s ago). Close-time consensus TRUE: the -30 s bin rounds to offset -20 s with 6 votes, meeting the 75% bar (6 of 8 participants). Median offset -20 s, close offset moves 0 → -5 s (quarter-step damping), resolution refines 30 → 20 s (agreement, ledger seq 104 divisible by 8), effective close offset -20 s.
- S-05 validation expiry: 4 accepted, 1 stale_seen (V-C, seen at +200 s). 3 laggards (V-A, V-B, V-E). After advancing 15 s, V-A (-170 s) and V-E (-179 s) expire as stale_past and V-C remains stale_seen — a validation signed 170 s in the past has 10 s of currency left. Close-time consensus FAILS; median offset -110 s, close offset moves 0 → -28 s.
- S-06 close-time disagreement: 8 accepted, 4 laggards. Close-time consensus FAILS: two bins tie at 4 votes each (offsets -50 s and +70 s); the earliest (-50 s) is adopted per the tie-break, but 4 < 7 needed for 75% of 9 participants. Fallback effective close is prior close + 1 s (offset -4 s) with closeFlags = sLCF_NoConsensusTime, median offset 0 s, resolution coarsens 30 → 60 s. canBeCurrent: parent close -240 s PASSES (within 5 min), parent close -400 s FAILS.
- S-07 NTP loss: 3 accepted. Close-time consensus TRUE (all peers agree; the +10 s consensus offset is a resolution-grid rounding artifact of the common close time). Drift trace over 7 rounds (measured offsets -12 s to -84 s): close offsets -3, -9, -18, -30, -45, -63, -84 s — quarter-step pull-back only. UNL expires at offset +300 s; the node keeps validating through round 5 (elapsed 300 s, expiry not yet earlier than now) and bows out in rounds 6-7.
- S-08 leap second / DST / malicious / rejoin: 6 accepted, 1 stale_future (V-M at +3600 s). Close-time consensus TRUE on the honest bin (offset +10 s). The malicious +3600 s proposal rounds to offset +3610 s, gets 1 vote, and loses; it is never dropped for being far-future because no such bound exists. The 1 s leap step is inside the +/-1 s dead band (offset after step: 0 s); DST has no effect (UTC seconds). Rejoin: a node returning at -400 s has canBeCurrent FAIL on return; after four quarter-step rounds its offset is +275 s, remaining error -125 s, and canBeCurrent PASSES.

## Totals

48 validators: 36 accepted, 5 stale_future, 4 stale_past, 3 stale_seen; 19 laggards, 19 stale proposals; close-time consensus in 3 of 8 scenarios; canBeCurrent 8 pass / 2 fail.

## Scenario grounds (assume vs MODELLED)

- **S-01**: Grounding: T-10 (three-clause predicate, strict edges), T-19 (seen == sign as authored), T-24 (75% close-time consensus). Simulator may assume a fast clock is accepted while inside the window. MODELLED: the seen time is modelled as authored; a peer-relayed copy is re-stamped by PeerImp (T-12), which can only ease the seen clause — see docs/methodology.md.
- **S-02**: Grounding: T-10 (CURRENT_EARLY edge), T-16 (laggard at 20 s). Simulator may assume the -180 s edge is strict (signTime == now - 180 s is stale). MODELLED: nothing beyond the predicate.
- **S-03**: Grounding: T-10 (CURRENT_WALL edge, seen clause), T-19. Simulator may assume the +300 s edge is strict. MODELLED: the seen-clause failure of the +180 s validator follows from seen == sign as authored (see methodology).
- **S-04**: Grounding: T-20/T-22/T-24 (rounded vote, 75% bar, tie-break), T-26/T-04 (median + quarter-step), T-21 (finer after agreement every 8 ledgers). Simulator may assume six peers at one rounded bin reach consensus. MODELLED: the +10 s rounding of the common close time (base % 30 = 20).
- **S-05**: Grounding: T-10 (re-evaluated after +15 s), T-16 (laggard), T-30 (proposal staleness). Simulator may assume a validation's remaining currency is exactly now + 180 s - signTime. MODELLED: the +15 s advance is a chosen probe, not an observed round length.
- **S-06**: Grounding: T-24 (75% bar, tie-break earliest wins), T-25 (fallback prior close + 1 s, sLCF_NoConsensusTime), T-21 (coarser after missed agreement), T-33 (5-minute canBeCurrent bound). Simulator may assume an evenly split vote fails consensus. MODELLED: the avalanche round gates do not apply to close time (D-04), so no stalled-round escape is modelled here.
- **S-07**: Grounding: T-04 (quarter-step damping), T-36 (UNL-expiry bow-out vs raw now()), T-02 (no NTP). Simulator may assume the offset moves by a quarter of the measured offset per round. MODELLED: the +12 s/round drift and the 7-round trace are scenario inputs; the live convergence rate is UNTESTABLE (T-42).
- **S-08**: Grounding: T-24 (vote only, no wall-clock bound — absence finding 7), T-04 (dead band), T-01 (UTC seconds, no DST), T-33 (canBeCurrent). Simulator may assume a far-future proposal loses the vote rather than being dropped. MODELLED: the leap-second dead-band inference (the last clause is inference, not code); the rejoin pull-back trace (measured offsets are scenario inputs).

## What the matrix does not show

Consensus declaration timing (T-28: 1.95 s / 15 s / 67% / 120 s abandon), the avalanche stalled-round rule (T-29), proposal refresh every 12 s (T-30), the 1 s heartbeat (T-31), and the SeqEnforcer (T-15) are cited in the rule catalog and verified by the probe but not exercised as separate scenarios; they are constants and predicates, not skew loads.
