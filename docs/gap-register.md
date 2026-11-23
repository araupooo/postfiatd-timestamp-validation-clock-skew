# Gap register

| ID | Gap | Rules |
| --- | --- | --- |
| G-01 | Live convergence rate of the close-offset feedback loop (T-04 + T-26) not measured — no live node was run (T-42). | T-42, T-04, T-26 |
| G-02 | Live close interval and close-time resolution actually observed not measured — requires a live ledger feed (T-43). | T-43, T-20, T-21 |
| G-03 | Simulation tests in `src/test/consensus/` not executed — the loop dynamics under real vote distributions were not observed. | T-42 |
| G-04 | Peer proposal arrival order / propagation timing not modelled — affects which copy of a validation each node sees first and when `seenTime` is stamped. | T-12, S-01 |
| G-05 | Median-offset behaviour under a Byzantine minority not quantified — the code states only that a median "resists a minority" (ConsensusTypes.h:191-200); the breaking fraction is not derived. | T-26 |
| G-06 | UNL-expiry + clock-skew interaction not exercised live — the bow-out uses raw `now()` (T-36) while currency checks use the adjusted clock (T-17). | T-36, T-17 |
| G-07 | `isCurrent()` boundary tests in `src/test/consensus/Validations_test.cpp:364-374` read but not executed. | T-10 |
| G-08 | `canBeCurrent()` startup-tolerance branch (check skipped when no validated ledger exists and candidate seq <= 10) not exercised as a separate scenario. | T-33 |

Counts: 8 gaps.
