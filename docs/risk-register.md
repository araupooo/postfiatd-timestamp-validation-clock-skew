# Risk register

Severity is a pack judgement (MODELLED), not a source fact: it rates how badly a simulator that made the stated wrong assumption would mispredict timestamp / clock-skew behaviour.

| ID | Severity | Risk | Rules |
| --- | --- | --- | --- |
| K-01 | HIGH | Simulator cites the `ConsensusParms` validation windows as live, so a future edit to one copy silently diverges from the enforced `ValidationParms` values. | T-34 |
| K-02 | HIGH | Simulator assumes a `ledgerMAX_CLOSE` bound exists, inventing a maximum close time the code never enforces. | T-35 |
| K-03 | HIGH | Simulator assumes peer close times are wall-clock bounded and drops far-future proposals, while the code only rounds and votes on them. | T-24 |
| K-04 | MEDIUM | Simulator measures the 5-minute validation window from the ledger's close time (the doc comment) instead of signing time vs `now` (the predicate). | T-05, T-10 |
| K-05 | MEDIUM | Simulator assumes NTP synchronises the node, understating the skew the windows and median must absorb. | T-02 |
| K-06 | MEDIUM | Simulator treats 67% (round consensus) and 80% (validation quorum) as the same threshold. | T-28, T-39 |
| K-07 | MEDIUM | Simulator assumes a 10 s close-time resolution by default, while the code default is 30 s. | T-20, T-38 |
| K-08 | MEDIUM | Simulator assumes validation expiry is 5 min from the ledger close time rather than signTime vs `now`, mis-timing expiry by the signing-to-close gap. | T-10 |
| K-09 | MEDIUM | Simulator assumes the median offset converges in one round, ignoring the quarter-step damping (a -400 s error is still -125 s after four rounds in S-08). | T-04, T-26 |
| K-10 | MEDIUM | Simulator assumes close-time consensus requires full agreement, missing the 75% bar and the agree-to-disagree fallback (prior close + 1 s, flagged). | T-24, T-25 |
| K-11 | MEDIUM | Simulator assumes a skewed node's validations are rejected network-wide, while acceptance is per receiver against each receiver's adjusted clock. | T-41, T-17 |
| K-12 | LOW | Simulator assumes leap seconds or DST are handled, while a 1 s step only lands in the +/-1 s dead band and DST has no effect at all. | T-01 |
| K-13 | LOW | Simulator assumes clock-skew alerts exist; the node logs the offset at info level with no threshold, so skew is silent. | T-26 |
| K-14 | LOW | Simulator relies on live close intervals/resolutions without a node; T-43 values are unknowable from source, so scenarios must parametrise them. | T-43 |

Counts: 14 risks (HIGH 3, MEDIUM 8, LOW 3).
