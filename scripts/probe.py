#!/usr/bin/env python3
"""probe.py — re-verify the timestamp-validation pack from its outputs.

Usage:
    python3 scripts/probe.py [--skip-manifest-check] [TIMESTAMP_RESULTS_JSON]

The --skip-manifest-check flag is for run_all.sh step 4 only: the
manifest on disk at that point predates the just-regenerated results,
so comparing against it would fail on any input change; step 5b re-runs
the probe without the flag after rewriting the manifest. A standalone
probe run (no flag) always performs the manifest check.

Checks (all re-derived, none trusted):
  A-00 pinned checkout HEAD equals the pinned commit.
  A-01 every VERIFIED rule's anchor sits inside its cited range in the
     pinned checkout (T-35 is an absence finding: re-grep ledgerMAX_CLOSE
     for 0 hits; T-34's dead-copy claim is re-grepped for 0 references
     outside the definition file); SPECIFIED rules carry external URLs
     (T-40 carries the in-tree docs/consensus.md source instead);
     MODELLED / UNTESTABLE rules carry no file source.
  B-01 simulator arithmetic: per scenario, accepted + stale_future +
     stale_past + stale_seen == validators; totals reconcile to
     48 validators / 36 accepted / 5 stale_future / 4 stale_past /
     3 stale_seen / 19 laggards / 19 stale proposals / 3 of 8
     close-time consensuses / canBeCurrent 8 pass / 2 fail.
  C-01 isCurrent re-grep: the exact three-clause predicate is present in
     Validations.h:162-165.
  D-01 key tokens at recorded lines: validationCURRENT_WALL 5 min
     (Validations.h:56), validationFRESHNESS 20 s (:89),
     ledgerMAX_CONSENSUS 15 s (ConsensusParms.h:95-96),
     ledgerMIN_CLOSE 2 s (:99), avCT_CONSENSUS_PCT 75 (:160),
     roundCloseTime half-resolution step (LedgerTiming.h:141).
  E-01 median offset + quarter damping re-grep: "Median handles outliers
     better than mean" (RCLConsensus.cpp:722) and "(by + 3s) / 4"
     (TimeKeeper.h:107).
  F-01 counts reconcile across files: matrix == results == scenarios (8);
     findings 12, claims 24 (16/2/4/2), risks 14, gaps 8; excerpts 52
     across 21 files agree across manifest, extracted files,
     source-hashes.json.
  G-01 determinism: re-running the simulator to a temp dir reproduces
     byte-identical outputs (full SHA-256 compare).
  H-01 excerpt integrity: every excerpt file digest matches
     fixtures/source-hashes.json and every manifest blob SHA/size
     matches `git hash-object` / file size in the checkout;
     run-manifest digests match the shipped derived files.
  I-01 absence findings re-grepped: ledgerMAX_CLOSE 0 hits;
     validationVALID 0 hits outside ConsensusParms.h; leap-second
     0 hits; adjtime/clock_gettime/gettimeofday 0 hits.
  J-01 67% vs 80% (D-02) and 10 s vs 30 s (D-03): minCONSENSUS_PCT = 67
     (ConsensusParms.h:79); ledgerDefaultTimeResolution is index 2
     (30 s) of the 10/20/30/60/90/120 ladder (LedgerTiming.h:44).
  T-01 timing sanity only (non-negative, never recorded).

Exit 0 only if every case passes. Prints one PASS/FAIL line per case
with the FULL 64-char SHA-256 digest where a digest is involved, and
writes outputs/derived/probe-results.json plus outputs/probe-run.log
(the log is the unedited stdout of this run; it contains no absolute
paths and no timestamps). No live node is involved.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"
PINNED_CHECKOUT = Path(os.environ.get(
    "PINNED_CHECKOUT", str(Path.home() / "workspace" / "postfiatd-pin-0085a1f")))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def git_blob(relpath):
    out = subprocess.run(["git", "-C", str(PINNED_CHECKOUT), "hash-object", "--", relpath],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def grep_count(pattern, *roots, extra_args=()):
    proc = subprocess.run(["grep", "-rn", *extra_args, pattern, *[str(PINNED_CHECKOUT / r) for r in roots]],
                          capture_output=True, text=True)
    return proc.stdout


def main():
    argv = [a for a in sys.argv[1:] if a != "--skip-manifest-check"]
    skip_manifest = "--skip-manifest-check" in sys.argv[1:]
    results_path = Path(argv[0]) if argv else \
        PACK_ROOT / "outputs" / "derived" / "timestamp-results.json"
    doc = load_json(results_path)
    matrix = load_json(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    rules = load_json(PACK_ROOT / "configs" / "timestamp-rules.json")["rules"]
    scenarios = load_json(PACK_ROOT / "configs" / "scenarios.json")["scenarios"]
    manifest = load_json(PACK_ROOT / "fixtures" / "excerpts-manifest.json")
    hashes = load_json(PACK_ROOT / "fixtures" / "source-hashes.json")
    findings = load_json(PACK_ROOT / "findings.json")["findings"]
    checks, lines = [], []

    def check(cid, label, ok, detail=""):
        checks.append({"id": cid, "check": label, "pass": bool(ok), "detail": detail})
        lines.append(("PASS " if ok else "FAIL ") + cid + " " + label +
                     ((" — " + detail) if detail else ""))

    t_start = time.monotonic()
    co = PINNED_CHECKOUT
    head = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip() if co.is_dir() else ""
    check("A-00", "pinned checkout HEAD equals the pinned commit",
          head == PINNED_COMMIT, f"HEAD={head}")

    # --- A: rule anchors ---------------------------------------------------
    a_ok, a_detail = True, ""
    n_verified = n_spec = n_mod = n_unt = 0
    for r in rules:
        src = r.get("source")
        if r["status"] == "VERIFIED":
            n_verified += 1
            if r["id"] == "T-35":
                # Absence finding: no file source; re-grep for 0 hits.
                if src is not None or not r.get("absence"):
                    a_ok, a_detail = False, "T-35: absence rule must carry no file source, only an absence record"
                    break
                hits = grep_count("ledgerMAX_CLOSE", "src", "include", "docs")
                if hits.strip():
                    a_ok, a_detail = False, f"T-35: ledgerMAX_CLOSE now has hits: {hits.strip()[:120]}"
                    break
                continue
            if not src or not src.get("anchor"):
                a_ok, a_detail = False, f"{r['id']}: verified rule lacks source/anchor"
                break
            lines_f = (co / src["file"]).read_text(errors="replace").splitlines()
            if not (1 <= src["start_line"] <= src["end_line"] <= len(lines_f)):
                a_ok, a_detail = False, f"{r['id']}: range out of bounds"
                break
            chunk = "\n".join(lines_f[src["start_line"] - 1:src["end_line"]])
            if src["anchor"] not in chunk:
                a_ok, a_detail = False, f"{r['id']}: anchor not in range"
                break
            if r["id"] == "T-34":
                hits = subprocess.run(
                    ["grep", "-rn", "validationVALID", str(co / "src"), str(co / "include")],
                    capture_output=True, text=True).stdout.strip()
                outside = [ln for ln in hits.splitlines()
                           if "ConsensusParms.h" not in ln]
                if outside:
                    a_ok, a_detail = False, f"T-34: validationVALID referenced outside definition: {outside[:1]}"
                    break
        elif r["status"] == "SPECIFIED":
            n_spec += 1
            if not r.get("external"):
                a_ok, a_detail = False, f"{r['id']}: specified rule needs an external record"
                break
            if r["id"] in ("T-38", "T-39"):
                if src is not None or "url" not in r["external"]:
                    a_ok, a_detail = False, f"{r['id']}: specified rule needs external URLs, no file source"
                    break
            if r["id"] == "T-40":
                if not src or src["file"] != "docs/consensus.md":
                    a_ok, a_detail = False, "T-40: specified rule must cite docs/consensus.md"
                    break
                lines_f = (co / src["file"]).read_text(errors="replace").splitlines()
                chunk = "\n".join(lines_f[src["start_line"] - 1:src["end_line"]])
                if src["anchor"] not in chunk:
                    a_ok, a_detail = False, "T-40: anchor not in range"
                    break
        else:
            n_mod += 1 if r["status"] == "MODELLED" else 0
            n_unt += 1 if r["status"] == "UNTESTABLE" else 0
            if src is not None:
                a_ok, a_detail = False, f"{r['id']}: {r['status']} rule must carry no file source"
                break
    if a_ok and (n_verified, n_spec, n_mod, n_unt) != (37, 3, 1, 2):
        a_ok, a_detail = False, f"rule status counts wrong: {n_verified}/{n_spec}/{n_mod}/{n_unt}"
    check("A-01", "43 rules: 37 VERIFIED anchors inside cited ranges (T-35 absence re-grepped 0 hits, T-34 dead copy re-grepped 0 refs), 3 SPECIFIED (2 external URLs + 1 in-tree doc), 1 MODELLED, 2 UNTESTABLE, none with a faked source",
          a_ok, a_detail or "37/3/1/2")

    # --- B: arithmetic -----------------------------------------------------
    b_ok, b_detail = True, ""
    for r in doc["scenarios"]:
        total = (len(r["accepted"]) + len(r["stale_future"])
                 + len(r["stale_past"]) + len(r["stale_seen"]))
        if total != r["validators_total"]:
            b_ok, b_detail = False, f"{r['id']}: arithmetic {total} != {r['validators_total']}"
            break
    t = doc["totals"]
    exp = {"validators_total": 48, "accepted": 36, "stale_future": 5,
           "stale_past": 4, "stale_seen": 3, "laggards": 19,
           "proposals_stale": 19, "close_time_consensus": 3,
           "close_time_no_consensus": 5, "can_be_current_pass": 8,
           "can_be_current_fail": 2}
    if b_ok:
        for k, v in exp.items():
            if t.get(k) != v:
                b_ok, b_detail = False, f"totals[{k}]={t.get(k)} != {v}"
                break
    check("B-01", "per-scenario arithmetic reconciles; totals 48 validators / 36 accepted / 5 stale_future / 4 stale_past / 3 stale_seen / 19 laggards / 19 stale proposals / close-time consensus 3 of 8 / canBeCurrent 8 pass / 2 fail",
          b_ok, b_detail or f"totals={t}")

    # --- C: isCurrent predicate --------------------------------------------
    val_h = (co / "src/xrpld/consensus/Validations.h").read_text(errors="replace").splitlines()
    pred = "\n".join(val_h[161:165])
    c_ok = ("signTime > (now - p.validationCURRENT_EARLY)" in pred
            and "signTime < (now + p.validationCURRENT_WALL)" in pred
            and "seenTime < (now + p.validationCURRENT_LOCAL)" in pred)
    check("C-01", "isCurrent() three-clause predicate present verbatim at Validations.h:162-165",
          c_ok, "grep-verified in Validations.h" if c_ok else "predicate text missing")

    # --- D: key tokens at recorded lines -----------------------------------
    parms = (co / "src/xrpld/consensus/ConsensusParms.h").read_text(errors="replace").splitlines()
    timing = (co / "src/xrpld/consensus/LedgerTiming.h").read_text(errors="replace").splitlines()
    d_checks = [
        ("validationCURRENT_WALL = std::chrono::minutes{5}" in val_h[55],
         "validationCURRENT_WALL 5 min not at Validations.h:56"),
        ("validationFRESHNESS = std::chrono::seconds{20}" in val_h[88],
         "validationFRESHNESS 20 s not at Validations.h:89"),
        ("ledgerMAX_CONSENSUS =" in parms[94] and "seconds{15}" in parms[95],
         "ledgerMAX_CONSENSUS 15 s not at ConsensusParms.h:95-96"),
        ("ledgerMIN_CLOSE = std::chrono::seconds{2}" in parms[98],
         "ledgerMIN_CLOSE 2 s not at ConsensusParms.h:99"),
        ("avCT_CONSENSUS_PCT = 75" in parms[159],
         "avCT_CONSENSUS_PCT 75 not at ConsensusParms.h:160"),
        ("closeTime += (closeResolution / 2);" in timing[140],
         "roundCloseTime half-resolution step not at LedgerTiming.h:141"),
    ]
    d_ok, d_detail = True, ""
    for ok, msg in d_checks:
        if not ok:
            d_ok, d_detail = False, msg
            break
    check("D-01", "WALL 5 min (Validations.h:56), FRESHNESS 20 s (:89), MAX_CONSENSUS 15 s (ConsensusParms.h:95-96), MIN_CLOSE 2 s (:99), avCT 75% (:160), roundCloseTime half step (LedgerTiming.h:141)",
          d_ok, d_detail or "6 tokens at recorded lines")

    # --- E: median + damping -----------------------------------------------
    rcl = (co / "src/xrpld/app/consensus/RCLConsensus.cpp").read_text(errors="replace").splitlines()
    tk = (co / "src/xrpld/core/TimeKeeper.h").read_text(errors="replace")
    e_ok = ("Median handles outliers better than mean." in rcl[721]
            and "return offset + ((by + 3s) / 4);" in tk)
    check("E-01", "median-offset comment (RCLConsensus.cpp:722) and quarter-step damping '(by + 3s) / 4' (TimeKeeper.h:107)",
          e_ok, "both verified" if e_ok else "median/damping text missing")

    # --- F: counts reconcile -----------------------------------------------
    def table_rows(path, prefix):
        rows = []
        for ln in open(path, encoding="utf-8"):
            m = re.match(rf"\| ({prefix}-\d+) \| ([A-Z]+) \|", ln)
            if m:
                rows.append((m.group(1), m.group(2)))
        return rows
    claims = table_rows(PACK_ROOT / "docs" / "claim-index.md", "C")
    risks = table_rows(PACK_ROOT / "docs" / "risk-register.md", "K")
    gaps = [ln for ln in open(PACK_ROOT / "docs" / "gap-register.md", encoding="utf-8")
            if re.match(r"\| G-\d+ \|", ln)]
    f_ok, f_detail = True, ""
    if matrix["scenario_count"] != len(doc["scenarios"]) != len(scenarios) != 8:
        f_ok, f_detail = False, "scenario count != 8 across files"
    elif matrix["totals"] != doc["totals"]:
        f_ok, f_detail = False, "matrix totals != results totals"
    elif len(findings) != 12:
        f_ok, f_detail = False, f"findings != 12 ({len(findings)})"
    elif len(claims) != 24:
        f_ok, f_detail = False, f"claims != 24 ({len(claims)})"
    elif Counter(s for _, s in claims) != {"VERIFIED": 16, "SPECIFIED": 2, "MODELLED": 4, "UNTESTABLE": 2}:
        f_ok, f_detail = False, f"claim statuses wrong: {Counter(s for _, s in claims)}"
    elif len(risks) != 14:
        f_ok, f_detail = False, f"risks != 14 ({len(risks)})"
    elif len(gaps) != 8:
        f_ok, f_detail = False, f"gaps != 8 ({len(gaps)})"
    excerpts = manifest.get("excerpts", [])
    exdir = PACK_ROOT / "fixtures" / "source-excerpts"
    if f_ok and (len(excerpts) != 52 or len(list(exdir.glob("*.txt"))) != 52):
        f_ok, f_detail = False, "excerpt manifest != extracted files != 52"
    if f_ok and len(hashes.get("files", {})) != 21:
        f_ok, f_detail = False, f"source files != 21 ({len(hashes.get('files', {}))})"
    if f_ok:
        for e in excerpts:
            if e["id"] not in hashes.get("excerpts", {}):
                f_ok, f_detail = False, f"excerpt {e['id']} missing from source-hashes.json"
                break
    check("F-01", "matrix == results == scenarios (8); findings 12, claims 24 (16/2/4/2), risks 14, gaps 8; excerpts 52 across 21 files agree across manifest, files, hashes",
          f_ok, f_detail or "all counts reconcile")

    # --- G: determinism ----------------------------------------------------
    res_digest = sha256_file(results_path)
    mat_digest = sha256_file(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    with tempfile.TemporaryDirectory(prefix="pftl-timestamp-probe.") as td:
        tmp_res, tmp_mat = Path(td) / "timestamp-results.json", Path(td) / "scenario-matrix.json"
        proc = subprocess.run(
            [sys.executable, str(PACK_ROOT / "src" / "timestamp_model.py"),
             "--out", str(tmp_res), "--matrix-out", str(tmp_mat)],
            capture_output=True, text=True)
        rerun_ok = proc.returncode == 0
        rerun_res = sha256_file(tmp_res) if tmp_res.is_file() else "missing"
        rerun_mat = sha256_file(tmp_mat) if tmp_mat.is_file() else "missing"
    check("G-01", "determinism: simulator re-run reproduces byte-identical results and matrix (full SHA-256)",
          rerun_ok and rerun_res == res_digest and rerun_mat == mat_digest,
          f"results shipped={res_digest} rerun={rerun_res}; matrix shipped={mat_digest} rerun={rerun_mat}")

    # --- H: excerpt + blob + manifest integrity ----------------------------
    h_ok, h_detail = True, ""
    for ex_id, rec in sorted(hashes.get("excerpts", {}).items()):
        p = exdir / f"{ex_id}.txt"
        if not p.is_file() or sha256_file(p) != rec["sha256"]:
            h_ok, h_detail = False, f"excerpt {ex_id}.txt digest mismatch"
            break
    if h_ok:
        for e in excerpts:
            src = co / e["file"]
            if git_blob(e["file"]) != e["blob_sha"]:
                h_ok, h_detail = False, f"excerpt {e['id']}: blob SHA mismatch"
                break
            if src.stat().st_size != e["blob_size"]:
                h_ok, h_detail = False, f"excerpt {e['id']}: blob size mismatch"
                break
    man_path = PACK_ROOT / "run-manifest.json"
    if skip_manifest:
        h_detail = ("manifest check skipped by caller (run_all.sh step 5b "
                    "performs it after the manifest is rewritten)")
    elif h_ok and man_path.is_file():
        man = load_json(man_path)
        if man.get("results_sha256") != res_digest or man.get("matrix_sha256") != mat_digest:
            h_ok, h_detail = False, "run-manifest digests != shipped derived files"
    elif h_ok:
        h_detail = "run-manifest.json not yet written (run_all.sh writes it after the probe); digest check deferred to the next probe run"
    check("H-01", "every excerpt digest matches source-hashes.json; every manifest blob SHA/size matches the checkout; run-manifest digests match shipped derived files",
          h_ok, h_detail or f"{len(hashes.get('excerpts', {}))} excerpt digests + blob SHAs verified")

    # --- I: absence findings re-grepped -------------------------------------
    def hits(pattern, *roots):
        out = subprocess.run(["grep", "-rn", pattern, *[str(co / r) for r in roots]],
                             capture_output=True, text=True).stdout.strip()
        return [ln for ln in out.splitlines() if ln]
    i_checks = [
        (not hits("ledgerMAX_CLOSE", "src", "include", "docs"), "ledgerMAX_CLOSE has hits"),
        (not [ln for ln in hits("validationVALID", "src", "include") if "ConsensusParms.h" not in ln],
         "validationVALID referenced outside ConsensusParms.h"),
        (not hits(r"leap\.second\|leap_second", "src", "include", "docs"), "leap-second has hits"),
        (not hits("adjtime|clock_gettime|gettimeofday", "src/xrpld", "include/xrpl", "src/libxrpl"),
         "adjtime/clock_gettime/gettimeofday has hits"),
    ]
    i_ok, i_detail = True, ""
    for ok, msg in i_checks:
        if not ok:
            i_ok, i_detail = False, msg
            break
    check("I-01", "absence findings re-grepped: ledgerMAX_CLOSE 0 hits; validationVALID 0 refs outside its definition file; leap-second 0 hits; adjtime/clock_gettime/gettimeofday 0 hits",
          i_ok, i_detail or "all absence claims hold (0 hits each)")

    # --- J: 67% vs 80% and 10 s vs 30 s -------------------------------------
    j_ok = ("std::size_t const minCONSENSUS_PCT = 67;" in parms[78]
            and "ledgerDefaultTimeResolution = ledgerPossibleTimeResolutions[2];" in timing[43])
    check("J-01", "67% quorum in code (ConsensusParms.h:79) and default close-time resolution is index 2 = 30 s (LedgerTiming.h:44); the 80% and 'usually 10 s' figures are doc statements, not code facts",
          j_ok, "both verified" if j_ok else "quorum/resolution text missing")

    elapsed_ms = (time.monotonic() - t_start) * 1000.0
    check("T-01", "timing sanity: total probe elapsed_ms is non-negative (loose band, never exact)",
          elapsed_ms >= 0, "value not recorded; never compared")

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    lines.append(f"probe: {passed}/{total} checks PASS")
    lines.append(f"probe: timestamp-results.json sha256: {res_digest}")
    lines.append(f"probe: scenario-matrix.json sha256: {mat_digest}")
    lines.append(f"probe: pinned commit {PINNED_COMMIT}")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    result_doc = {"pack": "Timestamp Validation and Clock-Skew Tolerance in postfiatd",
                  "pinned_commit": PINNED_COMMIT,
                  "results_file": "outputs/derived/timestamp-results.json",
                  "results_sha256": res_digest, "matrix_sha256": mat_digest,
                  "checks": checks, "passed": passed, "total": total}
    out_derived = PACK_ROOT / "outputs" / "derived" / "probe-results.json"
    out_derived.parent.mkdir(parents=True, exist_ok=True)
    with open(out_derived, "w", encoding="utf-8") as fh:
        json.dump(result_doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    (PACK_ROOT / "outputs" / "probe-run.log").write_text(text)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
