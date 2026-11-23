#!/usr/bin/env python3
"""timestamp_model.py — deterministic timestamp-validation / clock-skew simulator.

Usage:
    python3 src/timestamp_model.py [--out PATH] [--matrix-out PATH] [--help]
    PINNED_CHECKOUT=<path>  (default ~/workspace/postfiatd-pin-0085a1f)

The engine implements the pack's timestamp model, rules T-01..T-37 from
configs/timestamp-rules.json (each VERIFIED against the pinned checkout;
see docs/methodology.md for the simulated-vs-observed separation), in
this pipeline order per scenario:

  0  receiver clock (T-02/T-03/T-17): receiver_now = base + receiver_skew
     + close_offset. All currency checks are evaluated against this
     network-adjusted time, never raw wall time.
  1  isCurrent (T-10): a validator's validation is accepted iff
     signTime > now - 180 AND signTime < now + 300 AND (seenTime is zero
     OR seenTime < now + 180). The three failure modes are reported
     separately as stale_future / stale_past / stale_seen. The edges are
     strict: signTime == now + 300 and signTime == now - 180 are stale.
  2  laggards (T-16): a validator counts as offline/laggard when
     receiver_now >= seenTime + 20 (validationFRESHNESS).
  3  propose freshness (T-30): a peer proposal whose seen time is
     <= now - 20 is stale and removed.
  4  close-time vote (T-20/T-22/T-24): each validator proposes its own
     adjusted close time (base + skew); each proposal is rounded with
     roundCloseTime() at the scenario resolution and tallied. A bin needs
     participantsNeeded(participants, 50) votes to be adopted and
     participantsNeeded(participants, 75) to declare close-time consensus
     (participantsNeeded(n, pct) = max(1, (n*pct + pct/2)//100), integer
     arithmetic, Consensus.h:1484-1489). Bins are walked highest-time
     first, so among tied bins the earliest wins. With no peers,
     consensus is trivially true on our own rounded time.
  5  effective close time (T-23/T-25): effCloseTime() =
     max(roundCloseTime(consensus, resolution), prevClose + 1). Without
     close-time consensus the round does not accept; the agree-to-disagree
     fallback is prevClose + 1 s with closeTimeCorrect = false and
     closeFlags = sLCF_NoConsensusTime.
  6  median offset + damping (T-26/T-04): the lower weighted median of
     peer close times minus our own (self weight 1, each peer bin weighted
     by its vote count), applied with the quarter-step damping of
     adjustCloseTime(): by > 1 s -> offset + trunc((by+3)/4); by < -1 s ->
     offset + trunc((by-3)/4); otherwise offset decays to trunc(offset*3/4).
     C++ integer division truncates toward zero; this engine reproduces
     that (Python // would floor for negatives).
  7  resolution adaptation (T-21): no agreement -> next coarser bin
     (checked every ledger); agreement and ledgerSeq % 8 == 0 -> next
     finer bin.
  8  canBeCurrent (T-33): a candidate ledger is current only if
     |receiver closeTime - parentCloseTime| <= 300 s (the only
     ledger-level wall-clock bound in the tree). No wall-clock bound is
     applied to a peer proposal's close time or to a ledger's own close
     time at accept (absence findings 7/8): a far-future proposal is only
     voted down, never dropped for being far.
  9  scenario extras (MODELLED applications, labelled as such):
     S-05 re-evaluates isCurrent() after advance_s seconds; S-07 replays
     a multi-round drift trace and the UNL-expiry bow-out (T-36);
     S-08 models a 1 s leap-second step through the T-04 dead band, a
     malicious far-future proposal, and a rejoining node's quarter-step
     pull-back over four rounds.

Rules T-38/T-39/T-40 (SPECIFIED), T-41 (MODELLED) and T-42/T-43
(UNTESTABLE) are not engine rules; scenarios that touch them record
their model outputs and label them. The base time is a fixed synthetic
Ripple-epoch second; no wall-clock time is read by the simulator.

Inputs: configs/scenarios.json (scripted, synthetic skew loads — model
inputs, not observed network traffic). Outputs are deterministic:
sorted keys, no timestamps, no absolute paths, no measured timings.
Exit 0 only if every scenario reconciles
(accepted + stale_future + stale_past + stale_seen == validators).
"""
import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"
PINNED_CHECKOUT = Path(os.environ.get(
    "PINNED_CHECKOUT", str(Path.home() / "workspace" / "postfiatd-pin-0085a1f")))
PACK_NAME = "Timestamp Validation and Clock-Skew Tolerance in postfiatd"

# Validation windows (T-05..T-09), seconds.
CURRENT_WALL = 300
CURRENT_LOCAL = 180
CURRENT_EARLY = 180
SET_EXPIRES = 600
FRESHNESS = 20
# Proposal windows (T-30), seconds.
PROPOSE_FRESHNESS = 20
PROPOSE_INTERVAL = 12
# Close-time resolutions (T-20), seconds.
RESOLUTIONS = [10, 20, 30, 60, 90, 120]
DEFAULT_RESOLUTION = 30
# Consensus timing (T-28), milliseconds.
MIN_CONSENSUS_MS = 1950
MAX_CONSENSUS_MS = 15000
ABANDON_CONSENSUS_MS = 120000
ABANDON_FACTOR = 10
MIN_CONSENSUS_PCT = 67
# Close-time consensus (T-24).
AV_CT_CONSENSUS_PCT = 75
# canBeCurrent bound (T-33), seconds.
CAN_BE_CURRENT_S = 300
# Ledger gates (T-27).
MIN_CLOSE_S = 2
IDLE_INTERVAL_S = 15


def trunc_div(a, b):
    """C++ integer division: truncates toward zero (unlike Python //)."""
    return math.trunc(a / b)


def round_close_time(t, resolution):
    """T-22: round to the nearest multiple of the resolution, half up."""
    if t == 0:
        return 0
    t = t + resolution // 2
    return t - (t % resolution)


def eff_close_time(close_time, resolution, prior_close_time):
    """T-23: never earlier than the prior close time + 1 s."""
    if close_time == 0:
        return 0
    return max(round_close_time(close_time, resolution), prior_close_time + 1)


def participants_needed(participants, percent):
    """Consensus.h:1484-1489."""
    result = ((participants * percent) + (percent // 2)) // 100
    return result if result != 0 else 1


def adjust_close_time(offset, by):
    """T-04: quarter-step damping with a +/-1 s dead band."""
    if by > 1:
        return offset + trunc_div(by + 3, 4)
    if by < -1:
        return offset + trunc_div(by - 3, 4)
    return trunc_div(offset * 3, 4)


def median_close_offset(self_time, peer_bins):
    """T-26 / ConsensusTypes.h:207-260: lower weighted median minus self.

    peer_bins: list of (time, weight) with weight = vote count of the bin.
    Self has weight 1. The median is the earliest time at which the
    running weight reaches half the total weight.
    """
    total = 1 + sum(w for _, w in peer_bins)
    half = (total + 1) // 2
    ordered = sorted([(self_time, 1)] + list(peer_bins))
    tally = 0
    for t, w in ordered:
        tally += w
        if tally >= half:
            return t - self_time
    raise AssertionError("medianCloseOffset: median not found")


def is_current(sign_time, seen_time, now):
    """T-10: the exact three-clause acceptance window.

    seen_time None means the zero time point (seenTime == NetClock
    time point {}), which passes the third clause unconditionally.
    Returns (current, failure) with failure in
    {None, 'stale_future', 'stale_past', 'stale_seen'}.
    """
    if not (sign_time > now - CURRENT_EARLY):
        return False, "stale_past"
    if not (sign_time < now + CURRENT_WALL):
        return False, "stale_future"
    if seen_time is not None and not (seen_time < now + CURRENT_LOCAL):
        return False, "stale_seen"
    return True, None


def next_resolution(resolution, previous_agree, ledger_seq):
    """T-21: coarser after a missed agreement (every ledger), finer after
    agreement (every 8 ledgers)."""
    idx = RESOLUTIONS.index(resolution)
    if not previous_agree and ledger_seq % 1 == 0:
        if idx + 1 < len(RESOLUTIONS):
            return RESOLUTIONS[idx + 1]
        return resolution
    if previous_agree and ledger_seq % 8 == 0:
        if idx - 1 >= 0:
            return RESOLUTIONS[idx - 1]
        return resolution
    return resolution


def run_scenario(sc):
    base = sc["base_time"]
    receiver_now = base + sc["receiver_skew_s"] + sc["initial_close_offset_s"]
    resolution = sc["resolution_s"]
    prev_close = base + sc["prev_close_offset_s"]
    ledger_seq = sc["ledger_seq"]
    previous_agree = sc["previous_agree"]
    vals = sc["validators"]

    accepted, stale_future, stale_past, stale_seen = [], [], [], []
    laggards, proposals_stale = [], []
    for val in vals:
        sign = base + val["skew_s"]
        seen = None if val.get("seen_offset_s") is None else base + val["seen_offset_s"]
        if seen is None:
            seen = sign  # T-19: a locally created validation starts with seen == sign
        ok, fail = is_current(sign, seen, receiver_now)
        if ok:
            accepted.append(val["id"])
        elif fail == "stale_future":
            stale_future.append(val["id"])
        elif fail == "stale_past":
            stale_past.append(val["id"])
        else:
            stale_seen.append(val["id"])
        # T-16: live only while now < seen + FRESHNESS.
        if not (receiver_now < seen + FRESHNESS):
            laggards.append(val["id"])
        # T-30: peer proposal stale when seen <= now - PROPOSE_FRESHNESS.
        if seen <= receiver_now - PROPOSE_FRESHNESS:
            proposals_stale.append(val["id"])

    # --- close-time vote (T-24) -------------------------------------------
    self_close = receiver_now  # T-32: our proposal is our adjusted clock
    votes = {}
    for val in vals:
        rounded = round_close_time(base + val["skew_s"], resolution)
        votes[rounded] = votes.get(rounded, 0) + 1
    votes[round_close_time(self_close, resolution)] = \
        votes.get(round_close_time(self_close, resolution), 0) + 1
    participants = len(vals) + 1  # peers + self, proposing
    needed_weight = 50  # avalanche init state (T-29)
    thresh_vote = participants_needed(participants, needed_weight)
    thresh_consensus = participants_needed(participants, AV_CT_CONSENSUS_PCT)
    consensus_close = None
    have_consensus = False
    if not vals:
        have_consensus = True
        consensus_close = round_close_time(self_close, resolution)
    else:
        thresh = thresh_vote
        for t in sorted(votes, reverse=True):  # highest-time first
            v = votes[t]
            if v >= thresh:
                consensus_close = t
                thresh = v
                if thresh >= thresh_consensus:
                    have_consensus = True
    # --- effective close time / fallback (T-23/T-25) ------------------------
    if have_consensus and consensus_close is not None:
        eff = eff_close_time(consensus_close, resolution, prev_close)
        close_correct = True
        close_flags = 0
    else:
        eff = prev_close + 1
        close_correct = False
        close_flags = 1  # sLCF_NoConsensusTime
    # --- median offset + damping (T-26/T-04) --------------------------------
    peer_bins = [(t, w) for t, w in votes.items()
                 if t != round_close_time(self_close, resolution)]
    # A peer bin that coincides with our own rounded time still counts as
    # peer weight at that time; rebuild bins from the raw peer votes.
    peer_bins = []
    raw = {}
    for val in vals:
        r = round_close_time(base + val["skew_s"], resolution)
        raw[r] = raw.get(r, 0) + 1
    peer_bins = sorted(raw.items())
    median_offset = median_close_offset(self_close, peer_bins) if vals else 0
    new_offset = adjust_close_time(sc["initial_close_offset_s"], median_offset)
    res_next = next_resolution(resolution, have_consensus, ledger_seq)

    # --- canBeCurrent (T-33) ------------------------------------------------
    can_current = []
    for parent_off in sc.get("candidate_parent_close_offsets_s", [0]):
        parent_close = base + parent_off
        diff = abs(receiver_now - parent_close)
        can_current.append({"parent_close_offset_s": parent_off,
                            "abs_diff_s": diff,
                            "within_5min": diff <= CAN_BE_CURRENT_S,
                            "pass": diff <= CAN_BE_CURRENT_S})

    res = {
        "id": sc["id"], "title": sc["title"],
        "receiver_now_offset_s": receiver_now - base,
        "resolution_s": resolution,
        "validators_total": len(vals),
        "accepted": sorted(accepted),
        "stale_future": sorted(stale_future),
        "stale_past": sorted(stale_past),
        "stale_seen": sorted(stale_seen),
        "laggards": sorted(laggards),
        "proposals_stale": sorted(proposals_stale),
        "close_time_votes": {str(k - base): v for k, v in sorted(votes.items())},
        "participants": participants,
        "thresh_vote": thresh_vote,
        "thresh_consensus": thresh_consensus,
        "have_close_time_consensus": have_consensus,
        "consensus_close_offset_s": (consensus_close - base) if consensus_close is not None else None,
        "eff_close_offset_s": eff - base,
        "close_time_correct": close_correct,
        "close_flags": close_flags,
        "median_offset_s": median_offset,
        "adjust_close_time": {"measured_offset_s": median_offset,
                              "old_offset_s": sc["initial_close_offset_s"],
                              "new_offset_s": new_offset},
        "next_resolution_s": res_next,
        "can_be_current": can_current,
    }
    assert (len(accepted) + len(stale_future) + len(stale_past)
            + len(stale_seen) == len(vals)), "scenario arithmetic broke"

    # --- scenario extras ----------------------------------------------------
    if "advance_s" in sc:
        adv_now = receiver_now + sc["advance_s"]
        expired_after = []
        for val in vals:
            sign = base + val["skew_s"]
            seen = base + val["seen_offset_s"] if val.get("seen_offset_s") is not None else sign
            ok, fail = is_current(sign, seen, adv_now)
            if not ok:
                expired_after.append({"id": val["id"], "failure": fail})
        res["expiry_after_advance_s"] = {"advance_s": sc["advance_s"],
                                         "expired": sorted(e["id"] for e in expired_after),
                                         "failures": sorted(expired_after, key=lambda e: e["id"]),
                                         "modelled_note": "T-10 re-evaluated at now + advance_s; a validation signed 170 s in the past has 10 s of currency left at the start."}

    if "rounds" in sc:
        trace = []
        offset = sc["initial_close_offset_s"]
        for rnd in sc["rounds"]:
            t = rnd["round"] * sc["round_duration_s"]
            unl_expires = base + sc["unl_expires_at_offset_s"]
            now_t = base + t  # wall time advances; closeTime() = now + offset
            bowing_out = unl_expires < now_t  # T-36: expiry earlier than now()
            new_offset = adjust_close_time(offset, rnd["measured_offset_s"])
            trace.append({"round": rnd["round"], "elapsed_s": t,
                          "measured_offset_s": rnd["measured_offset_s"],
                          "old_offset_s": offset, "new_offset_s": new_offset,
                          "unl_expired": bowing_out})
            offset = new_offset
        res["drift_trace"] = {
            "rounds": trace,
            "final_offset_s": offset,
            "modelled_note": ("T-04 quarter-step damping applied once per round to the "
                              "measured median offset; T-36 bow-out evaluated against "
                              "raw now(), not the adjusted close time."),
        }

    if "malicious" in sc:
        mal = sc["malicious"]
        mal_close = base + mal["skew_s"]
        mal_rounded = round_close_time(mal_close, resolution)
        res["malicious_proposal"] = {
            "id": mal["id"], "proposed_close_offset_s": mal["skew_s"],
            "rounded_close_offset_s": mal_rounded - base,
            "votes_for_its_bin": votes.get(mal_rounded, 0),
            "won_vote": (have_consensus and consensus_close == mal_rounded),
            "validation_accepted": mal["id"] in accepted,
            "modelled_note": ("No wall-clock bound drops a far-future proposal "
                              "(absence finding 7): it is only rounded (T-22) and "
                              "voted on (T-24). Its validation is stale_future, but "
                              "the proposal itself still enters the vote."),
        }
        res["leap_second"] = {
            "step_s": sc["leap_step_s"],
            "inside_dead_band": abs(sc["leap_step_s"]) <= 1,
            "offset_after_step_s": adjust_close_time(0, sc["leap_step_s"]),
            "modelled_note": ("No leap-second handling exists (absence finding 4, "
                              "0 grep hits). A 1 s step is inside the T-04 +/-1 s "
                              "dead band, so the close offset decays by 3/4 instead "
                              "of stepping; that last clause is inference, not code."),
        }
        res["dst"] = {
            "effect": "none",
            "modelled_note": ("No DST/timezone handling exists on the consensus path "
                              "(absence finding 5, 0 grep hits in clock logic). All "
                              "timestamps are UTC seconds since the Ripple epoch (T-01)."),
        }
        rj = sc["rejoin"]
        offset = sc["initial_close_offset_s"]
        rj_trace = []
        for measured in rj["measured_offsets_s"]:
            new_offset = adjust_close_time(offset, measured)
            rj_trace.append({"measured_offset_s": measured,
                             "old_offset_s": offset, "new_offset_s": new_offset})
            offset = new_offset
        wall = base + rj["returning_skew_s"]
        res["rejoin"] = {
            "returning_skew_s": rj["returning_skew_s"],
            "close_time_on_return_s": wall - base,
            "can_be_current_on_return": abs((wall + sc["initial_close_offset_s"]) - base) <= CAN_BE_CURRENT_S,
            "trace": rj_trace,
            "final_offset_s": offset,
            "remaining_error_s": rj["returning_skew_s"] + offset,
            "can_be_current_after_pull": abs((wall + offset) - base) <= CAN_BE_CURRENT_S,
            "modelled_note": ("Quarter-step pull-back only (T-04/T-26): after four "
                              "rounds a -400 s error is still not closed. The "
                              "rejoining node's own validations are stale_past "
                              "until its adjusted clock re-enters the T-10 window."),
        }
    return res


def main():
    ap = argparse.ArgumentParser(description="Deterministic timestamp-validation / clock-skew simulator.")
    ap.add_argument("--out", default=str(PACK_ROOT / "outputs" / "derived" / "timestamp-results.json"))
    ap.add_argument("--matrix-out", default=str(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json"))
    args = ap.parse_args()
    checkout_ok = False
    if PINNED_CHECKOUT.is_dir():
        head = subprocess.run(["git", "-C", str(PINNED_CHECKOUT), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        if head != PINNED_COMMIT:
            print(f"timestamp_model: ERROR: pinned checkout HEAD {head} != {PINNED_COMMIT}",
                  file=sys.stderr)
            return 1
        checkout_ok = True
    else:
        print("timestamp_model: no pinned checkout found; running on the recorded model alone")
    scenarios = json.load(open(PACK_ROOT / "configs" / "scenarios.json"))["scenarios"]
    results = [run_scenario(sc) for sc in scenarios]
    totals = {
        "scenarios": len(results),
        "validators_total": sum(r["validators_total"] for r in results),
        "accepted": sum(len(r["accepted"]) for r in results),
        "stale_future": sum(len(r["stale_future"]) for r in results),
        "stale_past": sum(len(r["stale_past"]) for r in results),
        "stale_seen": sum(len(r["stale_seen"]) for r in results),
        "laggards": sum(len(r["laggards"]) for r in results),
        "proposals_stale": sum(len(r["proposals_stale"]) for r in results),
        "close_time_consensus": sum(1 for r in results if r["have_close_time_consensus"]),
        "close_time_no_consensus": sum(1 for r in results if not r["have_close_time_consensus"]),
        "can_be_current_pass": sum(1 for r in results for c in r["can_be_current"] if c["pass"]),
        "can_be_current_fail": sum(1 for r in results for c in r["can_be_current"] if not c["pass"]),
    }
    doc = {"pack": PACK_NAME,
           "pinned_commit": PINNED_COMMIT,
           "pinned_checkout_verified": checkout_ok,
           "windows_s": {"validationCURRENT_WALL": CURRENT_WALL,
                         "validationCURRENT_LOCAL": CURRENT_LOCAL,
                         "validationCURRENT_EARLY": CURRENT_EARLY,
                         "validationSET_EXPIRES": SET_EXPIRES,
                         "validationFRESHNESS": FRESHNESS,
                         "proposeFRESHNESS": PROPOSE_FRESHNESS,
                         "proposeINTERVAL": PROPOSE_INTERVAL},
           "resolutions_s": RESOLUTIONS,
           "consensus": {"minCONSENSUS_PCT": MIN_CONSENSUS_PCT,
                         "ledgerMIN_CONSENSUS_ms": MIN_CONSENSUS_MS,
                         "ledgerMAX_CONSENSUS_ms": MAX_CONSENSUS_MS,
                         "ledgerABANDON_CONSENSUS_ms": ABANDON_CONSENSUS_MS,
                         "ledgerABANDON_CONSENSUS_FACTOR": ABANDON_FACTOR,
                         "avCT_CONSENSUS_PCT": AV_CT_CONSENSUS_PCT,
                         "canBeCurrent_s": CAN_BE_CURRENT_S,
                         "ledgerMIN_CLOSE_s": MIN_CLOSE_S,
                         "ledgerIDLE_INTERVAL_s": IDLE_INTERVAL_S},
           "scenarios": results, "totals": totals}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    matrix = {"pack": PACK_NAME,
              "pinned_commit": PINNED_COMMIT,
              "scenario_count": len(results),
              "rows": [{"id": r["id"], "title": r["title"],
                        "validators": r["validators_total"],
                        "accepted": len(r["accepted"]),
                        "stale_future": len(r["stale_future"]),
                        "stale_past": len(r["stale_past"]),
                        "stale_seen": len(r["stale_seen"]),
                        "laggards": len(r["laggards"]),
                        "proposals_stale": len(r["proposals_stale"]),
                        "have_close_time_consensus": r["have_close_time_consensus"],
                        "consensus_close_offset_s": r["consensus_close_offset_s"],
                        "median_offset_s": r["median_offset_s"],
                        "new_close_offset_s": r["adjust_close_time"]["new_offset_s"],
                        "next_resolution_s": r["next_resolution_s"],
                        "can_be_current_pass": sum(1 for c in r["can_be_current"] if c["pass"]),
                        "can_be_current_fail": sum(1 for c in r["can_be_current"] if not c["pass"])}
                       for r in results],
              "totals": totals}
    mout = Path(args.matrix_out)
    mout.parent.mkdir(parents=True, exist_ok=True)
    with open(mout, "w") as fh:
        json.dump(matrix, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"timestamp_model: {len(results)} scenarios, "
          f"validators={totals['validators_total']} accepted={totals['accepted']} "
          f"stale_future={totals['stale_future']} stale_past={totals['stale_past']} "
          f"stale_seen={totals['stale_seen']} close_time_consensus={totals['close_time_consensus']}/"
          f"{totals['scenarios']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
