# Decision memo

## Decision

Adopt the 43-rule catalog (37 VERIFIED, 3 SPECIFIED, 1 MODELLED, 2 UNTESTABLE) as the pack's timestamp model, follow the code wherever xrpl.org docs disagree with it (30 s default resolution, not "usually 10 s"; 67% round consensus, not 80%), cite `Validations.h` — never `ConsensusParms.h` — for the validation windows, and label every model-only step as MODELLED rather than presenting it as source-derived.

## Why

- The 37 verified rules are each anchored to a grep-verified source range in the pinned tree, with 52 excerpts and blob SHAs re-checked by the probe.
- The highest-value corrections are the absences: there is no `ledgerMAX_CLOSE`, no NTP/SNTP client, no leap-second or DST handling, no wall-clock bound on peer proposal close times, and no wall-clock check on a ledger's own close time at accept. A simulator that invents any of those bounds mispredicts this fork on every scenario that touches skew (K-02, K-03).
- The `isCurrent()` predicate — not its doc comment — is the rule: the 5-minute window is measured from signing time against local `now` (F-01, K-04).
- The modelled tolerance (T-41) follows directly from the predicate plus the adjusted-clock `now()`: a validator up to ~5 minutes fast or ~3 minutes slow relative to the receiver's adjusted clock is still accepted, per receiver.

## What was not decided

- No live-network claim is made (T-42/T-43 UNTESTABLE).
- No convergence rate for the close-offset feedback loop is adopted: the quarter-step damping is verified, the live rate is not.
- No NTP discipline or leap-second smoothing is adopted: the node has none, and this pack does not invent one.
- No rejoin procedure beyond the verified median + damping steps is adopted; the S-08 rejoin trace is MODELLED.

## Consequences

If a live node becomes available, T-42/T-43 can be verified against observed rounds and recent validated ledgers (`close_time_resolution`), and the scenario parameters (base time, skews, resolutions) can be replaced with measured values. Until then the scenarios remain parametrised models.
