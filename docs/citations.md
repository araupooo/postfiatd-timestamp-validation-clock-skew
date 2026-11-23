# Citations

## Pinned-tree citations (primary)

All timestamp rules cite the pinned postfiatd tree (commit `0085a1ff885d6a446369cf73a4430f75af22be55`), verified by `grep -n` on the local checkout. The full rule-to-source mapping is `configs/timestamp-rules.json`; the excerpt table is `docs/excerpts.md`. Key citations re-verified by grep in this pack:

- `isCurrent()` three-clause predicate — `src/xrpld/consensus/Validations.h:162-165` (E10).
- Validation windows 5/3/3 min, sets 10 min, freshness 20 s — `src/xrpld/consensus/Validations.h:50-89` (E05–E09).
- `closeTime() = now() + closeOffset_`, quarter-step damping — `src/xrpld/core/TimeKeeper.h:69-116` (E03, E04).
- Close-time resolutions 10/20/30/60/90/120 s, default 30 s — `src/xrpld/consensus/LedgerTiming.h:35-47` (E21); rounding and effective close time — `:124-169` (E23, E24).
- Close-time vote, 75% consensus — `src/xrpld/consensus/Consensus.h:1507-1641` (E25); `avCT_CONSENSUS_PCT = 75` — `src/xrpld/consensus/ConsensusParms.h:160` (E50).
- Median close offset — `src/xrpld/app/consensus/RCLConsensus.cpp:704-728` (E27).
- `canBeCurrent()` 5-minute parent-close bound — `src/xrpld/app/ledger/detail/LedgerMaster.cpp:364-398` (E34).
- Consensus timing 1.95 s / 15 s / 67% / 120 s — `src/xrpld/consensus/Consensus.cpp:176-270` (E29); constants — `src/xrpld/consensus/ConsensusParms.h:78-114` (E39).
- Dead `ConsensusParms` validation windows — `src/xrpld/consensus/ConsensusParms.h:45-66` (E35); zero references outside the definition file (T-34).
- In-tree design doc, "Effective Close Time" — `docs/consensus.md:145-169` (E38).

## Absence citations (0-hit grep results, re-checked by the probe)

| # | Search (from the pinned checkout root) | Result |
| --- | --- | --- |
| A-01 | `grep -rn "ledgerMAX_CLOSE" src/ include/ docs/` | 0 hits (T-35) |
| A-02 | `grep -rn "validationVALID" src/ include/` excluding `src/xrpld/consensus/ConsensusParms.h` | 0 hits (T-34) |
| A-03 | `grep -rni "sntp_servers\|SNTP" src/xrpld/ include/` (excluding tests) | Only 2 hits, both non-functional: `src/xrpld/core/ConfigSections.h:82` (config-section name) and `src/xrpld/core/TimeKeeper.h:51` (doc comment). No `sntp_servers`/`SECTION_SNTP` read in `Config.cpp`/`Config.h`. |
| A-04 | `grep -rni "leap.second\|leap_second" src/ include/ docs/` | 0 hits |
| A-05 | `grep -rn "localtime\|tzset\|timezone" src/xrpld/ include/xrpl/ src/libxrpl/ --include=*.cpp --include=*.h` (excluding tests) | 0 hits in clock logic; the single `timezone` hit is `src/xrpld/app/main/Main.cpp:850-865`, a Windows-only startup workaround that feeds no consensus clock. |
| A-06 | `grep -rn "adjtime\|clock_gettime\|gettimeofday" src/xrpld/ include/xrpl/ src/libxrpl/ --include=*.cpp --include=*.h` | 0 hits |
| A-07 | `grep -rn "closeTime" src/xrpld/consensus/Consensus.h` filtered for wall/now/bound/check/valid | 0 hits — no wall-clock bound on a peer proposal's close time |
| A-08 | No wall-clock check on a ledger's own close time at accept | Only `canBeCurrent()` on the parent close time (T-33); `doAccept()`/`buildLedger()` take the consensus close time as given. |
| A-09 | No monotonic-clock enforcement of validation signing times | Only the `SeqEnforcer` (T-15, steady clock) and the `Validations` expiry clocks use a monotonic clock. |
| A-10 | No clock-skew alerting | The offset is logged at info level with no threshold or metric (`RCLConsensus.cpp:724-725`). |

## External citations (non-pinned-tree sources)

| # | URL | What it establishes |
| --- | --- | --- |
| C-01 | https://xrpl.org/docs/concepts/ledgers/ledger-structure/ | Ledger Header: the close time is "the official timestamp when this ledger's contents were finalized. This number is rounded off by a number of seconds, usually 10." Source for T-38. |
| C-02 | https://xrpl.org/docs/concepts/consensus-protocol/ | Trust-Based Validation: "As long as fewer than 20% of trusted validators are faulty, consensus can continue unimpeded; and confirming an invalid transaction would require over 80% of trusted validators to collude." Source for T-39. |

RFC 5905 (NTP) is NOT cited as a used source: `grep -rni "5905\|RFC 5\|rfc.*ntp\|NTP.*RFC" src/ include/ docs/` returns 0 relevant hits (only RFC 5737 documentation address ranges in `src/libxrpl/beast/net/IPAddressV4.cpp`). NTP is recorded as ABSENT (A-03), not as a source the node uses.

## Limits stated honestly

- No live node was run; the close-offset feedback loop's live convergence rate (T-42) and the live close interval/resolution actually observed (T-43) are UNTESTABLE from source alone.
- The 80% figure (C-02) is the *validation* quorum concept, not the 67% `minCONSENSUS_PCT` used to declare transaction-set consensus in `checkConsensus` (T-28). The two must not be conflated (D-02).
- The "usually 10 s" rounding (C-01) describes steady-state live behaviour; the code default is 30 s (T-20), bridged by the adaptation mechanism (T-21) (D-03).
- `docs/consensus.md` threshold naming (`AV_XXX_CONSENSUS_PCT`) is stale: the code has no `AV_*` constants; the table is `avalancheCutoffs` (T-29) (D-04).
- `docs/consensus.md` consensus-declaration conditions are a simplified account of an older shape of the logic; `checkConsensus` (T-28) is authoritative (D-06).
- Cross-validator behaviour (which copy of a validation each node saw first, proposal arrival order) is inherently unobservable from a single checkout.
- XRPL docs sometimes disagree with the code. Where they disagree, this pack follows the code and says so.
