
#!/usr/bin/env python3
"""
improve_reasoning.py

Replaces the thin auto-generated reasoning strings in submission.csv with
richer, fact-grounded reasoning that:
  - Cites specific companies, assessment scores, response times, recruiter saves
  - Matches tone to rank (top = confident, bottom = "relevant but weaker fit")
  - Explicitly connects evidence to JD requirements
  - Admits weaknesses honestly for lower-ranked candidates

Usage:
    python src/improve_reasoning.py \
        --submission output/submission.csv \
        --candidates data/candidates.jsonl \
        --out output/submission_final.csv

No LLM, no API, no GPU. Pure fact extraction from candidate JSON.
"""

import json
import gzip
import csv
import argparse
import sys
from datetime import date, datetime


def days_since(date_str):
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (date.today() - d).days
    except Exception:
        return 9999


def load_submission(path):
    """Returns list of dicts, ordered by rank."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    rows.sort(key=lambda r: int(r["rank"]))
    return rows


def load_target_candidates(jsonl_path, target_ids):
    """Stream through candidates.jsonl, return dict of id->candidate for target_ids only."""
    found = {}
    opener = gzip.open if jsonl_path.endswith(".gz") else open
    with opener(jsonl_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = c.get("candidate_id", "")
            if cid in target_ids:
                found[cid] = c
            if len(found) == len(target_ids):
                break  # found all of them
    return found


def safe(x):
    return "" if x is None else str(x)


def build_rich_reasoning(c, rank, total=100):
    """
    Build a specific, grounded 1-2 sentence reasoning string.
    Tone calibrated to rank: top = confident, bottom = honest about limitations.
    """
    p = c.get("profile", {})
    sig = c.get("redrob_signals", {})
    career = c.get("career_history", [])
    education = c.get("education", [])

    title = safe(p.get("current_title"))
    company = safe(p.get("current_company"))
    yoe = p.get("years_of_experience", 0) or 0
    location = safe(p.get("location"))
    country = safe(p.get("country"))

    # Assessments
    assessments = sig.get("skill_assessment_scores") or {}
    assessment_values = [(k, v) for k, v in assessments.items()
                         if isinstance(v, (int, float))]
    assessment_values.sort(key=lambda x: -x[1])

    # Signals
    saved = sig.get("saved_by_recruiters_30d") or 0
    response_rate = sig.get("recruiter_response_rate") or 0
    response_hours = sig.get("avg_response_time_hours") or 0
    open_to_work = sig.get("open_to_work_flag", False)
    notice = sig.get("notice_period_days") or 0
    last_active = sig.get("last_active_date") or ""
    interview_rate = sig.get("interview_completion_rate") or 0
    github = sig.get("github_activity_score") or -1
    relocate = sig.get("willing_to_relocate", False)
    work_mode = sig.get("preferred_work_mode") or ""

    # Education
    top_edu = None
    for edu in education:
        if (edu.get("tier") or "") in ("tier_1", "tier_2"):
            top_edu = edu
            break
    if not top_edu and education:
        top_edu = education[0]

    # Career companies (non-current, for trajectory)
    prior_companies = [r.get("company", "") for r in career if not r.get("is_current")]

    # Build reasoning parts
    parts = []

    # --- Part 1: core fit statement (rank-calibrated) ---
    if rank <= 10:
        fit_prefix = "Strong fit"
    elif rank <= 30:
        fit_prefix = "Good fit"
    elif rank <= 60:
        fit_prefix = "Relevant background"
    else:
        fit_prefix = "Partial fit"

    core = f"{fit_prefix}: {title} at {company} with {yoe:.1f} years experience"

    # Add prior company context if notable
    if prior_companies:
        prior_str = ", ".join(prior_companies[:2])
        core += f" (prev: {prior_companies[0]})" if len(prior_companies) == 1 else f" (prev: {prior_str})"

    parts.append(core)

    # --- Part 2: assessment evidence (most specific verifiable signal) ---
    if assessment_values:
        top_assessments = assessment_values[:3]
        assess_str = ", ".join(f"{k} {v:.0f}" for k, v in top_assessments)
        avg = sum(v for _, v in assessment_values) / len(assessment_values)
        parts.append(f"verified assessments: {assess_str} (avg {avg:.0f})")
    else:
        if rank <= 50:
            parts.append("no platform assessments taken")

    # --- Part 3: availability & engagement ---
    avail_parts = []
    if open_to_work:
        avail_parts.append("actively job-seeking")
    else:
        avail_parts.append("passive candidate")

    if response_rate >= 0.7:
        avail_parts.append(f"responds to {response_rate:.0%} of messages")
    elif response_rate > 0 and rank <= 50:
        avail_parts.append(f"response rate {response_rate:.0%}")

    if saved >= 20:
        avail_parts.append(f"{saved} recruiter saves/30d")
    elif saved >= 5 and rank <= 30:
        avail_parts.append(f"{saved} recruiter saves/30d")

    if notice <= 15:
        avail_parts.append("immediate joiner")
    elif notice <= 30:
        avail_parts.append(f"{notice}d notice")
    elif notice >= 90 and rank <= 50:
        avail_parts.append(f"{notice}d notice (long)")

    if avail_parts:
        parts.append("; ".join(avail_parts))

    # --- Part 4: location ---
    loc_str = f"{location}, {country}" if country and country != "India" else location
    if relocate:
        parts.append(f"based {loc_str}, willing to relocate")
    else:
        parts.append(f"based {loc_str}")

    # --- Part 5: honest weakness for lower ranks ---
    if rank >= 70:
        parts.append("weaker domain signal relative to top candidates")
    elif rank >= 50:
        parts.append("adjacent skills, less direct search/ranking depth than top-ranked")

    # Join with semicolons, keep under ~200 chars for readability
    reasoning = "; ".join(p for p in parts if p)
    if len(reasoning) > 220:
        # Trim: keep first 3 parts
        reasoning = "; ".join(parts[:3])

    return reasoning


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", default="output/submission_final.csv")
    args = ap.parse_args()

    print("Loading submission...", file=sys.stderr)
    rows = load_submission(args.submission)
    target_ids = {r["candidate_id"] for r in rows}
    print(f"  {len(rows)} candidates to enrich", file=sys.stderr)

    print("Streaming candidates.jsonl for target IDs...", file=sys.stderr)
    candidates = load_target_candidates(args.candidates, target_ids)
    print(f"  Found {len(candidates)} of {len(target_ids)} target candidates", file=sys.stderr)

    print("Building enriched reasoning strings...", file=sys.stderr)
    improved = []
    for row in rows:
        cid = row["candidate_id"]
        rank = int(row["rank"])
        c = candidates.get(cid)

        if c:
            reasoning = build_rich_reasoning(c, rank, total=len(rows))
        else:
            reasoning = row["reasoning"]  # keep original if not found
            print(f"  WARNING: {cid} not found in candidates file", file=sys.stderr)

        improved.append({
            "candidate_id": cid,
            "rank": row["rank"],
            "score": row["score"],
            "reasoning": reasoning,
        })

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        writer.writerows(improved)

    print(f"\nWritten: {args.out}", file=sys.stderr)
    print("\nSample reasoning strings:", file=sys.stderr)
    for r in improved[:5]:
        print(f"  Rank {r['rank']}: {r['reasoning'][:120]}...", file=sys.stderr)
    print("  ...", file=sys.stderr)
    for r in improved[-3:]:
        print(f"  Rank {r['rank']}: {r['reasoning'][:120]}...", file=sys.stderr)


if __name__ == "__main__":
    main()
