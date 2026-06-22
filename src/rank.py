#!/usr/bin/env python3
"""
rank.py  —  Redrob Intelligent Candidate Discovery & Ranking
============================================================

Produces a valid submission.csv (exactly 100 rows, sorted by score descending)
for the Senior AI Engineer role.

Usage:
    python rank.py --candidates data/candidates.jsonl --out output/submission.csv

Runtime: ~3-5 minutes on CPU for 100K candidates (single-threaded, streaming).

Design philosophy (from the JD analysis):
  - The real signal is RARE, SPECIFIC retrieval/ranking vocabulary (NDCG, MRR,
    "search engineer" title, learning-to-rank) — NOT common buzzwords like
    "embeddings" or "FAISS" which the dataset shows are near-uniformly distributed.
  - A Recommendation Engineer who never says "RAG" may be a stronger match than a
    Marketing Manager whose skills list is full of vector DB keywords.
  - Behavioral / platform signals (open_to_work, last_active_date, recruiter response
    rate, interview completion) are important but only AMPLIFY a real domain signal,
    never substitute for one.
  - Hard disqualifiers: consulting-only career, honeypot flags (impossible duplicate
    achievements, anachronistic certs, degree-institution mismatches), very recent
    AI-only exposure with no pre-LLM depth, senior-manager-only career (no coding).
"""

import json
import re
import csv
import sys
import argparse
import gzip
import os
from datetime import date, datetime
from collections import defaultdict


# ---------------------------------------------------------------------------
# 1. Signal Term Banks
# ---------------------------------------------------------------------------
# Calibrated against full-100K frequency analysis:
#   - STRONG  = rare, role-specific; a single hit is meaningful
#   - MEDIUM  = moderately distinctive; present in real search/ranking roles
#   - WEAK    = common / noise-adjacent; only meaningful in combination
#
# Weights are additive but GATED: recruiter/assessment bonuses only apply
# when signal_score > 0, so keyword-stuffers with zero domain signal can't
# buy their way in via high engagement metrics.

STRONG_TERMS = {
    r"\bndcg\b":                      ("ndcg",                  40),
    r"\bmrr\b":                       ("mrr",                   40),
    r"\bsearch engineer\b":           ("search engineer",        35),
    r"\branking engineer\b":          ("ranking engineer",       35),
    r"\brelevance engineer\b":        ("relevance engineer",     35),
    r"\bmatching engineer\b":         ("matching engineer",      35),
    r"\brecommendation engineer\b":   ("recommendation engineer",35),
    r"\brecommender engineer\b":      ("recommender engineer",   35),
    r"\bquery understanding\b":       ("query understanding",    30),
    r"\bsearch infrastructure\b":     ("search infrastructure",  30),
    r"\bpersonalization\b":           ("personalization",        25),
    r"\blearning.to.rank\b":          ("learning-to-rank",       30),
    r"\bcollaborative filtering\b":   ("collaborative filtering",25),
    r"\binformation retrieval\b":     ("information retrieval",  20),
    r"\bclick.?through rate\b":       ("click-through rate",     20),
    r"\bmap@\b":                      ("map@k",                  20),
}

MEDIUM_TERMS = {
    r"\bbm25\b":                      ("bm25",            15),
    r"\belasticsearch\b":             ("elasticsearch",   12),
    r"\bopensearch\b":                ("opensearch",      12),
    r"\bqdrant\b":                    ("qdrant",          12),
    r"\bweaviate\b":                  ("weaviate",        12),
    r"\bmilvus\b":                    ("milvus",          12),
    r"\branking\b":                   ("ranking",         10),
    r"\brecommendation\b":            ("recommendation",  10),
    r"\brecommender\b":               ("recommender",      8),
    r"\bsemantic search\b":           ("semantic search",  8),
    r"\bvector search\b":             ("vector search",    8),
    r"\bvector database\b":           ("vector database",  8),
    r"\bsearch relevance\b":          ("search relevance", 8),
    r"\bclick.?through\b":            ("click-through",    8),
}

WEAK_TERMS = {
    r"\bretrieval\b":                 ("retrieval",         5),
    r"\bembeddings?\b":               ("embeddings",         3),
    r"\bpinecone\b":                  ("pinecone",           3),
    r"\bfaiss\b":                     ("faiss",              3),
    r"\bvector db\b":                 ("vector db",          3),
    r"\bmatching system\b":           ("matching system",    4),
    r"\bmatching engine\b":           ("matching engine",    4),
}


def _compile(bank):
    return [(re.compile(pat, re.IGNORECASE), label, weight)
            for pat, (label, weight) in bank.items()]


STRONG_C = _compile(STRONG_TERMS)
MEDIUM_C = _compile(MEDIUM_TERMS)
WEAK_C   = _compile(WEAK_TERMS)


def score_text(text, compiled_bank):
    """Return (total_weight, list_of_hit_labels) for unique term matches."""
    if not text:
        return 0, []
    hits = {}
    for pattern, label, weight in compiled_bank:
        if label not in hits and pattern.search(text):
            hits[label] = weight
    return sum(hits.values()), sorted(hits.keys())


# ---------------------------------------------------------------------------
# 2. Hard disqualifier lists
# ---------------------------------------------------------------------------

CONSULTING_BLOCKLIST = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "mindtree", "hcl technologies", "hcl", "tech mahindra",
    "ltimindtree", "l&t infotech", "mphasis", "hexaware", "kpit",
    # BPM/IT services firms — JD explicitly excludes consulting/services companies
    "genpact",
}

# Titles that suggest person is no longer hands-on (hard disqualifier if
# current title ONLY contains these and career has zero coding signals)
NON_CODING_TITLE_PATTERNS = [
    re.compile(r"\b(chief|vp|vice president|svp|evp|cto|ceo)\b", re.I),
    re.compile(r"\bdirector\b", re.I),
]

# Titles that are hard marketing/non-engineering disqualifiers
MARKETING_TITLE_PATTERNS = [
    re.compile(r"\b(marketing manager|content writer|graphic designer|"
               r"accountant|sales executive|hr manager|civil engineer|"
               r"mechanical engineer|customer support|operations manager|"
               r"project manager|business analyst)\b", re.I),
]

# Certifications: tech -> earliest possible year
TECH_EARLIEST_YEAR = {
    "langchain": 2022,
    "gpt-4": 2023,
    "gpt4": 2023,
    "llamaindex": 2022,
    "llama index": 2022,
    "qdrant": 2021,
    "weaviate": 2019,
    "pinecone": 2021,
    "stable diffusion": 2022,
    "chatgpt": 2022,
    "mistral": 2023,
    "llama 2": 2023,
    "llama2": 2023,
}

# US institutions that don't use Indian degree nomenclature
US_INSTITUTIONS = {
    "stanford university", "massachusetts institute of technology", "mit",
    "harvard university", "carnegie mellon university", "uc berkeley",
    "university of california, berkeley", "princeton university",
    "yale university", "cornell university", "columbia university",
    "caltech", "california institute of technology", "university of michigan",
    "georgia institute of technology", "georgia tech",
}
NON_US_DEGREES = {"b.tech", "m.tech", "b.e.", "m.e.", "b.sc", "m.sc", "b.e", "m.e"}

# Institution founding years — enrollment before founding is impossible.
# Deliberately conservative: only institutions with well-known, unambiguous
# founding dates. Matching is case-insensitive substring to handle slight
# name variations (e.g. "IIT Hyderabad" vs "Indian Institute of Technology Hyderabad").
INSTITUTION_FOUNDED_YEAR = {
    # New IITs (established 2008 by GoI)
    "iit hyderabad":     2008,
    "iit gandhinagar":   2008,
    "iit ropar":         2008,
    "iit patna":         2008,
    "iit bhubaneswar":   2008,
    "iit jodhpur":       2008,
    "iit indore":        2009,
    "iit mandi":         2009,
    # IISERs
    "iiser pune":        2006,
    "iiser kolkata":     2006,
    "iiser mohali":      2007,
    "iiser bhopal":      2008,
    "iiser tirupati":    2015,
    # Well-known private tech universities with known founding
    "shiv nadar university": 2011,
    "ashoka university":     2014,
    "plaksha university":    2021,
    "krea university":       2018,
}

# Expected duration (years) for common degree types.
# start_year/end_year must be within ±1 of the expected range.
DEGREE_DURATION_RULES = {
    # degree_keyword (lowercase substring match) -> (min_years, max_years)
    "b.tech":  (3, 5),
    "b.e":     (3, 5),
    "b.e.":    (3, 5),
    "be ":     (3, 5),
    "b.sc":    (2, 4),
    "b.sc.":   (2, 4),
    "m.tech":  (1, 3),
    "m.e":     (1, 3),
    "m.e.":    (1, 3),
    "mba":     (1, 3),
    "m.sc":    (1, 3),
    "ph.d":    (3, 8),
    "phd":     (3, 8),
    "doctor":  (3, 8),
}


# ---------------------------------------------------------------------------
# 3. Helper utilities
# ---------------------------------------------------------------------------

def safe_str(x):
    return "" if x is None else str(x)


def safe_lower(x):
    return safe_str(x).strip().lower()


def load_candidates(path):
    """
    Yields candidate dicts from either:
      - JSONL format (one JSON object per line) — e.g. candidates.jsonl
      - JSON array format (a single list of objects) — e.g. sample_candidates.json

    Auto-detects format by peeking at the first non-whitespace character.
    Supports plain and gzip-compressed files (.gz).
    """
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        raw = f.read(1)
        # Peek: if the file starts with '[' it's a JSON array
        if raw.strip() == "[":
            f.seek(0)
            try:
                data = json.load(f)
                if isinstance(data, list):
                    yield from data
                elif isinstance(data, dict):
                    yield data
            except json.JSONDecodeError:
                pass
        else:
            # JSONL: stream line by line (memory-efficient for large files)
            f.seek(0)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue


def all_text(c):
    """Single searchable string across all profile fields."""
    p = c.get("profile", {})
    parts = [
        safe_str(p.get("current_title")),
        safe_str(p.get("headline")),
        safe_str(p.get("summary")),
    ]
    for r in c.get("career_history", []):
        parts.append(safe_str(r.get("title")))
        parts.append(safe_str(r.get("description")))
    for s in c.get("skills", []):
        parts.append(safe_str(s.get("name")))
    return " ".join(parts)


def career_text_only(c):
    """Descriptions + titles only — excludes skills (avoids keyword stuffing)."""
    p = c.get("profile", {})
    parts = [safe_str(p.get("current_title")), safe_str(p.get("headline"))]
    for r in c.get("career_history", []):
        parts.append(safe_str(r.get("title")))
        parts.append(safe_str(r.get("description")))
    return " ".join(parts)


def total_career_months(c):
    return sum(r.get("duration_months", 0) for r in c.get("career_history", []))


def days_since(date_str, ref=None):
    """Days since date_str (YYYY-MM-DD). Returns 9999 if unparseable."""
    if ref is None:
        ref = date.today()
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (ref - d).days
    except Exception:
        return 9999


# ---------------------------------------------------------------------------
# 4. Integrity / honeypot checks
# ---------------------------------------------------------------------------

WHOLE_ROLE_DURATION_RE = re.compile(
    r"\b(?:across|over|in|during|for)\s+(?:roughly|about|approximately)?\s*"
    r"(?:my\s+|the\s+(?:last|past)\s+)?(\d+(?:\.\d+)?)\s*(months?|years?|yrs?)\s+"
    r"(?:here|in this role|at this (?:company|role)|tenure)\b"
    r"|"
    r"\bowned\s+(?:all\s+\w+\s+)?across\s+(?:roughly|about)?\s*(\d+(?:\.\d+)?)\s*(months?|years?|yrs?)\b",
    re.IGNORECASE,
)


def check_self_contradicting_duplicate(c):
    """
    Flag if a STRONG/MEDIUM-signal role description appears verbatim under
    two different jobs — a logical impossibility (same achievement claimed twice).
    Generic/filler duplicates are NOT flagged (proven generator noise).
    """
    roles = c.get("career_history", [])
    if len(roles) < 2:
        return False, []

    seen = {}
    flagged = []
    for r in roles:
        desc = r.get("description", "") or ""
        if not desc:
            continue
        if desc in seen:
            # Only flag if the duplicated text itself has domain signal
            w_s, _ = score_text(desc, STRONG_C)
            w_m, _ = score_text(desc, MEDIUM_C)
            if w_s + w_m > 0:
                flagged.append(
                    f"{r.get('title','')}@{r.get('company','')} "
                    f"<-> {seen[desc]}"
                )
        else:
            seen[desc] = f"{r.get('title','')}@{r.get('company','')}"

    return len(flagged) > 0, flagged


def check_anachronistic_cert(c):
    evidence = []
    for cert in (c.get("certifications") or []):
        name = safe_lower(cert.get("name", ""))
        year = cert.get("year")
        if not isinstance(year, int):
            continue
        for term, earliest in TECH_EARLIEST_YEAR.items():
            if term in name and year < earliest:
                evidence.append(
                    f"'{cert.get('name')}' dated {year} but '{term}' "
                    f"not public before {earliest}"
                )
    return len(evidence) > 0, evidence


def check_degree_mismatch(c):
    evidence = []
    for edu in (c.get("education") or []):
        institution = safe_lower(edu.get("institution", ""))
        degree = safe_lower(edu.get("degree", ""))
        if institution in US_INSTITUTIONS and degree in NON_US_DEGREES:
            evidence.append(
                f"'{edu.get('degree')}' at '{edu.get('institution')}'"
            )
    return len(evidence) > 0, evidence


def check_anachronistic_institution(c):
    """
    Flags education entries where the start_year predates the founding year
    of the institution. Example: IIT Hyderabad (founded 2008) with start_year=2006
    is a logical impossibility — the institution did not exist yet.

    Uses INSTITUTION_FOUNDED_YEAR, a conservative list of institutions with
    well-known, unambiguous founding dates. Treated as a HARD honeypot flag
    (same category as anachronistic certs) since it is a flat impossibility.
    """
    evidence = []
    for edu in (c.get("education") or []):
        institution = safe_lower(edu.get("institution", ""))
        start_year = edu.get("start_year")
        if not isinstance(start_year, int):
            continue
        for inst_key, founded in INSTITUTION_FOUNDED_YEAR.items():
            if inst_key in institution and start_year < founded:
                evidence.append(
                    f"Enrolled at '{edu.get('institution')}' in {start_year}, "
                    f"but it was founded in {founded}"
                )
    return len(evidence) > 0, evidence


def check_degree_duration_anomaly(c):
    """
    Flags education entries where the degree duration (end_year - start_year)
    is implausibly short or long for the claimed degree type.
    Example: B.E. completed in 3 years (should be 4) is suspicious.

    Conservative: only flags clear outliers using DEGREE_DURATION_RULES.
    Treated as a soft penalty (not hard disqualifier) since edge cases exist
    (e.g. credit transfer, part-time study). Does NOT apply if end_year or
    start_year is missing.
    """
    evidence = []
    for edu in (c.get("education") or []):
        degree = safe_lower(edu.get("degree", ""))
        start_year = edu.get("start_year")
        end_year = edu.get("end_year")
        if not isinstance(start_year, int) or not isinstance(end_year, int):
            continue
        duration = end_year - start_year
        if duration <= 0:
            continue  # separate check handles end < start
        for deg_key, (min_y, max_y) in DEGREE_DURATION_RULES.items():
            if deg_key in degree:
                if duration < min_y:
                    evidence.append(
                        f"'{edu.get('degree')}' at '{edu.get('institution')}': "
                        f"completed in {duration} yrs (min expected {min_y})"
                    )
                elif duration > max_y:
                    evidence.append(
                        f"'{edu.get('degree')}' at '{edu.get('institution')}': "
                        f"claimed {duration} yrs (max expected {max_y})"
                    )
                break  # only apply the first matching rule
    return len(evidence) > 0, evidence


def check_duration_contradiction(c, tolerance=0.5):
    evidence = []
    for r in c.get("career_history", []):
        desc = r.get("description", "") or ""
        actual_months = r.get("duration_months")
        if not desc or not isinstance(actual_months, (int, float)) or actual_months <= 0:
            continue
        for match in WHOLE_ROLE_DURATION_RE.finditer(desc):
            groups = [g for g in match.groups() if g is not None]
            if len(groups) < 2:
                continue
            try:
                num = float(groups[0])
            except ValueError:
                continue
            unit = groups[1].lower()
            mentioned_months = num * 12 if unit.startswith(("year", "yr")) else num
            if mentioned_months < 1:
                continue
            diff_ratio = abs(mentioned_months - actual_months) / actual_months
            if diff_ratio > tolerance:
                evidence.append(
                    f"{r.get('title','')}@{r.get('company','')}: "
                    f"claims ~{num:g} {unit} but duration_months={actual_months:.0f}"
                )
    return len(evidence) > 0, evidence


def check_experience_inflation(c):
    """
    Compares profile.years_of_experience against the actual sum of
    career_history[*].duration_months to detect inflated experience claims.

    Pattern caught: CAND_0039754 claims 16.2 years in the profile field,
    but career_history totals only 37+40+21 = 98 months = 8.17 years.
    The candidate's own summary text also says "8.3 years" — a direct
    self-contradiction between two fields in the same record.

    Thresholds (calibrated conservatively):
      > 7 years gap  → HARD honeypot flag (>~50% inflation, not explainable
                        by career breaks, freelancing, or rounding)
      > 4 years gap  → strong soft penalty
      > 2 years gap  → moderate soft penalty (gaps, freelancing plausible)

    Also checks whether the summary text contains a self-reported years figure
    that contradicts the profile years_of_experience field (±2 yr tolerance).

    Returns (inflation_level: str, gap_years: float, evidence: list[str])
      inflation_level: "hard_honeypot" | "strong" | "moderate" | "none"
    """
    p = c.get("profile", {})
    profile_years = p.get("years_of_experience")
    if not isinstance(profile_years, (int, float)) or profile_years <= 0:
        return "none", 0.0, []

    career_months = sum(
        r.get("duration_months", 0)
        for r in c.get("career_history", [])
        if isinstance(r.get("duration_months"), (int, float))
    )
    career_years = career_months / 12.0
    gap = profile_years - career_years

    evidence = []

    # Primary check: gap between claimed and career-history-derived years
    if gap > 7:
        level = "hard_honeypot"
        evidence.append(
            f"Profile claims {profile_years:.1f} yrs experience but career history "
            f"totals only {career_years:.1f} yrs (gap={gap:.1f} yrs)"
        )
    elif gap > 4:
        level = "strong"
        evidence.append(
            f"Profile claims {profile_years:.1f} yrs but career history = "
            f"{career_years:.1f} yrs (gap={gap:.1f} yrs)"
        )
    elif gap > 2:
        level = "moderate"
        evidence.append(
            f"Profile claims {profile_years:.1f} yrs but career history = "
            f"{career_years:.1f} yrs (gap={gap:.1f} yrs)"
        )
    else:
        level = "none"

    # Secondary check: summary text self-reporting a different year count
    # Look for patterns like "X years of experience" or "X-year career"
    summary = p.get("summary") or ""
    _years_in_text_re = re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(?:-\s*)?years?\s+(?:of\s+)?(?:hands.on\s+)?experience\b",
        re.IGNORECASE
    )
    for m in _years_in_text_re.finditer(summary):
        try:
            text_years = float(m.group(1))
        except ValueError:
            continue
        if abs(text_years - profile_years) > 2:
            evidence.append(
                f"Summary says '{text_years:.1f} years of experience' but "
                f"profile.years_of_experience={profile_years:.1f} "
                f"(contradicts own field)"
            )
            # Upgrade level if not already flagged hard
            if level == "none":
                level = "moderate"

    return level, round(gap, 2), evidence


def is_consulting_only(c):
    roles = c.get("career_history", [])
    if not roles:
        return False
    for r in roles:
        comp = safe_lower(r.get("company", ""))
        if not any(block in comp for block in CONSULTING_BLOCKLIST):
            return False  # at least one non-consulting role
    return True


def is_marketing_or_non_tech(c):
    """Hard disqualifier: current title is clearly a non-engineering role."""
    title = safe_lower(c.get("profile", {}).get("current_title", ""))
    for pat in MARKETING_TITLE_PATTERNS:
        if pat.search(title):
            return True
    return False


def has_product_company_experience(c):
    """
    Returns True if the candidate has at least ONE role at a non-consulting
    company (i.e., a product company), False if 100% consulting.
    """
    return not is_consulting_only(c)


# ---------------------------------------------------------------------------
# 5. Main scoring function
# ---------------------------------------------------------------------------

def compute_candidate_score(c):
    """
    Returns a dict with candidate_id, final_score, and diagnostic fields.
    Higher score = better fit for the Senior AI Engineer role.

    Score components (all additive):
    A. Domain signal score  — rare retrieval/ranking vocabulary in career text
    B. Skills signal boost  — domain vocab in skills list (up to a cap, to
       prevent pure keyword-stuffing from dominating)
    C. Assessment evidence  — verified platform skill scores
    D. Recruiter engagement — saved by recruiters, response rate, interview completion
    E. Availability bonus   — open_to_work, last_active_date recency
    F. Experience fit       — years in JD sweet spot (5-9), product-co experience
    G. Education tier       — mild bonus for tier_1 institutions
    H. GitHub activity      — mild bonus for recent open-source work

    Hard disqualifiers (applied as huge negative penalties, effectively -∞):
    - Marketing/non-tech title with no domain signal
    - 100% consulting career
    - Honeypot: self-contradicting duplicate achievement claim
    - Honeypot: anachronistic certification (cert dated before tech existed)
    - Honeypot: anachronistic institution enrollment (enrolled before institution founded)

    Soft penalties:
    - No skill assessments taken (zero assessment penalty)
    - Degree-institution nomenclature mismatch (B.Tech at Stanford etc.)
    - Degree duration anomaly (B.E. completed in 3 years instead of 4)
    - Description-vs-duration self-contradiction
    - open_to_work = False
    - Last active > 90 days ago
    - Notice period > 60 days
    """
    cid = c["candidate_id"]
    p = c.get("profile", {})
    sig = c.get("redrob_signals", {})

    # --- Basic profile fields ---
    years_exp = p.get("years_of_experience") or 0
    current_title = safe_str(p.get("current_title"))
    notice_period = sig.get("notice_period_days") or 0

    # --- Integrity checks (run first; hard disqualifiers exit early) ---
    is_honeypot_dup, dup_evidence          = check_self_contradicting_duplicate(c)
    is_anachronistic, anach_evidence       = check_anachronistic_cert(c)
    is_anach_inst, anach_inst_evidence     = check_anachronistic_institution(c)
    exp_level, exp_gap, exp_evidence       = check_experience_inflation(c)
    has_deg_mismatch, deg_evidence         = check_degree_mismatch(c)
    has_deg_duration, deg_dur_evidence     = check_degree_duration_anomaly(c)
    has_dur_contradiction, dur_evidence    = check_duration_contradiction(c)

    honeypot_penalty = 0
    honeypot_reason = ""
    if is_honeypot_dup:
        honeypot_penalty = 2000
        honeypot_reason = "DUPLICATE_ACHIEVEMENT: " + "; ".join(dup_evidence)
    if is_anachronistic:
        honeypot_penalty = max(honeypot_penalty, 2000)
        honeypot_reason += " | ANACHRONISTIC_CERT: " + "; ".join(anach_evidence)
    if is_anach_inst:
        honeypot_penalty = max(honeypot_penalty, 2000)
        honeypot_reason += " | ANACHRONISTIC_INSTITUTION: " + "; ".join(anach_inst_evidence)
    if exp_level == "hard_honeypot":
        # >7 yr gap between claimed and career-history years — not explainable
        # by career breaks; equivalent confidence to an impossible cert date
        honeypot_penalty = max(honeypot_penalty, 2000)
        honeypot_reason += " | EXPERIENCE_INFLATION: " + "; ".join(exp_evidence)

    # --- Domain signal scoring ---
    # Career text (title + descriptions) — primary signal source
    career_txt = career_text_only(c)
    w_strong_career, strong_hits_career = score_text(career_txt, STRONG_C)
    w_medium_career, medium_hits_career = score_text(career_txt, MEDIUM_C)
    w_weak_career, weak_hits_career    = score_text(career_txt, WEAK_C)

    career_signal = w_strong_career + w_medium_career + w_weak_career

    # Skills text — secondary; capped to avoid keyword-stuffers dominating
    skills_txt = " ".join(safe_str(s.get("name")) for s in c.get("skills", []))
    w_strong_skills, _ = score_text(skills_txt, STRONG_C)
    w_medium_skills, _ = score_text(skills_txt, MEDIUM_C)
    w_weak_skills, _   = score_text(skills_txt, WEAK_C)

    # Skills signal is downweighted and capped (max 60 pts from skills alone)
    skills_signal_raw = (w_strong_skills * 0.5) + (w_medium_skills * 0.4) + (w_weak_skills * 0.2)
    skills_signal = min(skills_signal_raw, 60)

    # Total domain signal
    signal_score = career_signal + skills_signal
    has_signal = signal_score > 0

    # Penalty for titles that are clearly non-engineering (marketing, accounting, etc.)
    # UNLESS they have real domain signal in their career text (the "hidden fit" case)
    non_tech_title = is_marketing_or_non_tech(c)
    non_tech_title_penalty = 500 if (non_tech_title and career_signal < 30) else 0

    # --- Consulting-only penalty ---
    consulting_only = is_consulting_only(c)
    consulting_penalty = 300 if consulting_only else 0

    # --- Skill assessment evidence (verified, harder to fake) ---
    assessments = sig.get("skill_assessment_scores") or {}
    assessment_values = [v for v in assessments.values()
                         if isinstance(v, (int, float))]
    assessment_count = len(assessment_values)
    assessment_avg = sum(assessment_values) / len(assessment_values) if assessment_values else 0
    assessment_max = max(assessment_values) if assessment_values else 0

    # Zero assessment penalty when signal exists but no verified backing
    zero_assessment_penalty = 30 if (has_signal and assessment_count == 0) else 0

    # Assessment bonus: weighted combination of count, average, max
    # Gated on having domain signal to prevent a Marketing Manager with high
    # assessment scores from outranking a genuine search engineer
    if has_signal:
        assessment_bonus = (
            assessment_avg * 0.4          # average quality
            + assessment_max * 0.2        # peak performance
            + assessment_count * 4        # breadth of verified skills
        )
    else:
        assessment_bonus = 0

    # --- Recruiter / behavioral engagement ---
    saved_30d          = sig.get("saved_by_recruiters_30d") or 0
    response_rate      = sig.get("recruiter_response_rate") or 0
    interview_rate     = sig.get("interview_completion_rate") or 0
    open_to_work       = sig.get("open_to_work_flag", False)
    github_score       = sig.get("github_activity_score") or -1
    last_active_str    = sig.get("last_active_date") or ""
    applications_30d   = sig.get("applications_submitted_30d") or 0
    profile_complete   = sig.get("profile_completeness_score") or 0

    # Gated on signal to prevent pure engagement-signal candidates from dominating
    if has_signal:
        recruiter_bonus = (
            saved_30d * 1.2
            + response_rate * 25
            + interview_rate * 15
            + (applications_30d * 0.5)
        )
        github_bonus = max(0, github_score) * 0.3 if github_score >= 0 else 0
    else:
        recruiter_bonus = 0
        github_bonus    = 0

    # Availability signals
    last_active_days = days_since(last_active_str) if last_active_str else 9999
    if open_to_work:
        availability_bonus = 20
    else:
        availability_bonus = -15  # passive candidates still surfaced but lower priority

    # Recency penalty: not seen for 90+ days is a strong signal of unavailability
    if last_active_days > 180:
        recency_penalty = 40
    elif last_active_days > 90:
        recency_penalty = 20
    else:
        recency_penalty = 0

    # Notice period: prefer sub-30d; penalize 60d+
    if notice_period <= 30:
        notice_bonus = 10
    elif notice_period <= 60:
        notice_bonus = 0
    else:
        notice_bonus = -10

    # --- Experience fit ---
    if 5 <= years_exp <= 9:
        experience_fit = 20   # sweet spot
    elif 4 <= years_exp <= 12:
        experience_fit = 10   # acceptable band
    elif years_exp < 3:
        experience_fit = -20  # too junior
    else:
        experience_fit = 0

    # --- Education tier (mild signal only) ---
    edu_bonus = 0
    for edu in (c.get("education") or []):
        tier = safe_lower(edu.get("tier", ""))
        if tier == "tier_1":
            edu_bonus = max(edu_bonus, 8)
        elif tier == "tier_2":
            edu_bonus = max(edu_bonus, 4)

    # --- Soft penalties ---
    degree_mismatch_penalty      = 30 if has_deg_mismatch else 0
    deg_duration_anomaly_penalty = 20 if has_deg_duration else 0
    dur_contradiction_penalty    = 25 if has_dur_contradiction else 0
    # Experience inflation soft penalties (hard case already covered above)
    if exp_level == "strong":
        exp_inflation_penalty = 150   # 4-7 yr gap — major credibility issue
    elif exp_level == "moderate":
        exp_inflation_penalty = 60    # 2-4 yr gap — notable but could be career break
    else:
        exp_inflation_penalty = 0

    # --- Final composite score ---
    final_score = (
        signal_score
        + assessment_bonus
        + recruiter_bonus
        + github_bonus
        + availability_bonus
        + experience_fit
        + edu_bonus
        + notice_bonus
        - zero_assessment_penalty
        - recency_penalty
        - consulting_penalty
        - honeypot_penalty
        - degree_mismatch_penalty
        - deg_duration_anomaly_penalty
        - dur_contradiction_penalty
        - exp_inflation_penalty
        - non_tech_title_penalty
    )

    # Collect human-readable strong hits for reasoning
    all_strong = sorted(set(strong_hits_career))
    all_medium = sorted(set(medium_hits_career))

    return {
        "candidate_id":              cid,
        "final_score":               round(final_score, 2),
        "signal_score":              round(signal_score, 2),
        "career_signal":             round(career_signal, 2),
        "skills_signal":             round(skills_signal, 2),
        "strong_hits":               "|".join(all_strong),
        "medium_hits":               "|".join(all_medium),
        "assessment_bonus":          round(assessment_bonus, 2),
        "recruiter_bonus":           round(recruiter_bonus, 2),
        "assessment_count":          assessment_count,
        "assessment_avg":            round(assessment_avg, 1),
        "assessment_max":            round(assessment_max, 1),
        "saved_by_recruiters_30d":   saved_30d,
        "recruiter_response_rate":   round(response_rate, 2),
        "open_to_work":              open_to_work,
        "last_active_days":          last_active_days,
        "notice_period_days":        notice_period,
        "years_of_experience":       years_exp,
        "current_title":             current_title,
        "current_company":           safe_str(p.get("current_company")),
        "is_honeypot":               (is_honeypot_dup or is_anachronistic
                                       or is_anach_inst
                                       or exp_level == "hard_honeypot"),
        "honeypot_reason":           honeypot_reason.strip(" |"),
        "consulting_only":           consulting_only,
        "exp_inflation_level":       exp_level,
        "exp_inflation_gap_yrs":     exp_gap,
        "exp_inflation_evidence":    "; ".join(exp_evidence),
        "has_degree_mismatch":       has_deg_mismatch,
        "has_deg_duration_anomaly":  has_deg_duration,
        "deg_duration_evidence":     "; ".join(deg_dur_evidence),
        "has_anach_institution":     is_anach_inst,
        "anach_inst_evidence":       "; ".join(anach_inst_evidence),
        "has_dur_contradiction":     has_dur_contradiction,
    }


# ---------------------------------------------------------------------------
# 6. Cross-candidate near-duplicate sibling detection
# ---------------------------------------------------------------------------

def find_near_duplicate_siblings(candidate_desc_sets):
    """
    Candidates sharing 1+ identical role descriptions are likely 'template
    twins' stamped from the same generator template. Penalize the lower-
    scoring twin to avoid wasting top-100 slots on redundant records.

    Threshold is 1+ (not 2+) to catch the CAND_0046525 pattern: only ONE
    of the two descriptions is template-copied (the other is unique), but
    that single shared description is still a generator fabrication flag.

    Input: dict of candidate_id -> frozenset of description strings
    Returns: dict of candidate_id -> list of sibling candidate_ids
    """
    desc_to_cands = defaultdict(set)
    for cid, descs in candidate_desc_sets.items():
        for desc in descs:
            if desc and len(desc) > 50:  # ignore very short / empty descriptions
                desc_to_cands[desc].add(cid)

    sibling_counts = defaultdict(lambda: defaultdict(int))
    for desc, cids in desc_to_cands.items():
        if len(cids) < 2:
            continue
        cids_list = list(cids)
        for i in range(len(cids_list)):
            for j in range(i + 1, len(cids_list)):
                a, b = cids_list[i], cids_list[j]
                sibling_counts[a][b] += 1
                sibling_counts[b][a] += 1

    return {
        cid: [other for other, cnt in others.items() if cnt >= 1]
        for cid, others in sibling_counts.items()
    }


# ---------------------------------------------------------------------------
# 7. Reasoning string builder
# ---------------------------------------------------------------------------

def build_reasoning(row):
    """Produce a concise one-sentence reasoning for the submission CSV."""
    parts = []

    title = row["current_title"]
    yoe   = row["years_of_experience"]
    parts.append(f"{title} ({yoe:.1f} yrs)")

    strong = row["strong_hits"]
    medium = row["medium_hits"]
    if strong:
        parts.append(f"strong signals: {strong}")
    elif medium:
        parts.append(f"medium signals: {medium[:60]}")

    if row["assessment_count"] > 0:
        parts.append(
            f"{row['assessment_count']} assessments avg={row['assessment_avg']:.0f}"
        )

    if row["open_to_work"]:
        parts.append("open-to-work")

    if row["recruiter_response_rate"] >= 0.7:
        parts.append(f"resp={row['recruiter_response_rate']:.2f}")

    if row["consulting_only"]:
        parts.append("(consulting-only penalty)")

    return "; ".join(parts)


# ---------------------------------------------------------------------------
# 8. Main pipeline
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Rank candidates for Redrob Senior AI Engineer role"
    )
    ap.add_argument("--candidates", required=True,
                    help="Path to candidates.jsonl (or .jsonl.gz)")
    ap.add_argument("--out", default="output/submission.csv",
                    help="Output submission CSV path")
    ap.add_argument("--top_n", type=int, default=100,
                    help="Number of candidates to include in submission (default 100)")
    ap.add_argument("--debug_out", default="output/full_scores.csv",
                    help="Full scoring output for debugging (all candidates with signal)")
    args = ap.parse_args()

    print("=" * 70, file=sys.stderr)
    print("Redrob Candidate Ranker", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"Input:  {args.candidates}", file=sys.stderr)
    print(f"Output: {args.out}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    results = []
    candidate_desc_sets = {}  # for cross-candidate duplicate detection (signal pool only)
    total_scanned = 0

    print("Pass 1: scoring all candidates...", file=sys.stderr, flush=True)

    for c in load_candidates(args.candidates):
        total_scanned += 1

        row = compute_candidate_score(c)

        # Keep ALL candidates with any domain signal OR with a very high score
        # (so we don't accidentally drop edge cases), but skip obvious zeros
        # with hard disqualifiers to save memory
        if row["signal_score"] > 0 or row["final_score"] > 50:
            results.append(row)
            # Track descriptions for cross-candidate dedup (signal pool only)
            candidate_desc_sets[row["candidate_id"]] = frozenset(
                r.get("description", "") or ""
                for r in c.get("career_history", [])
            )

        if total_scanned % 10_000 == 0:
            print(f"  ...{total_scanned:,} scanned | "
                  f"{len(results):,} with signal", file=sys.stderr, flush=True)

    print(f"\nTotal scanned:          {total_scanned:,}", file=sys.stderr)
    print(f"Candidates with signal: {len(results):,}", file=sys.stderr)

    # --- Pass 2: cross-candidate near-duplicate detection ---
    print("\nPass 2: checking for template-twin near-duplicates...", file=sys.stderr, flush=True)
    siblings_map = find_near_duplicate_siblings(candidate_desc_sets)
    print(f"Candidates with a near-duplicate sibling: {len(siblings_map):,}", file=sys.stderr)

    # Sort by current final_score to identify which twin is weaker
    results.sort(key=lambda r: -r["final_score"])
    score_by_id = {r["candidate_id"]: r["final_score"] for r in results}

    sibling_penalty = 50  # soft penalty for the weaker template twin
    for cid, sibling_ids in siblings_map.items():
        my_score = score_by_id.get(cid)
        if my_score is None:
            continue
        sibling_scores = [score_by_id[s] for s in sibling_ids if s in score_by_id]
        if sibling_scores and my_score <= max(sibling_scores):
            # This is the weaker or tied sibling — penalize
            for r in results:
                if r["candidate_id"] == cid:
                    r["final_score"] = round(r["final_score"] - sibling_penalty, 2)
                    break

    # Re-sort after sibling penalty — primary: score desc, secondary: candidate_id asc (tiebreak)
    results.sort(key=lambda r: (-r["final_score"], r["candidate_id"]))

    # --- Diagnostics ---
    honeypots = sum(1 for r in results if r["is_honeypot"])
    consulting = sum(1 for r in results if r["consulting_only"])
    print(f"Honeypots in signal pool:    {honeypots:,}", file=sys.stderr)
    print(f"Consulting-only in pool:     {consulting:,}", file=sys.stderr)

    # --- Write debug output (full scored pool) ---
    os.makedirs(os.path.dirname(args.debug_out) or ".", exist_ok=True)
    if results:
        with open(args.debug_out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results[:2000])  # write top 2000 for inspection
        print(f"\nDebug scores written to: {args.debug_out} (top 2000)", file=sys.stderr)

    # --- Select final top-N (non-honeypot first, then backfill if needed) ---
    # Primary sort: exclude hard honeypots from top slots unless we must
    clean   = [r for r in results if not r["is_honeypot"]]
    flagged = [r for r in results if     r["is_honeypot"]]
    # Both lists already sorted by (-score, candidate_id) from the sort above

    if len(clean) >= args.top_n:
        final_top = clean[:args.top_n]
    else:
        # Not enough clean candidates — backfill with flagged (sorted by score)
        needed = args.top_n - len(clean)
        final_top = clean + flagged[:needed]
        print(f"\nWARNING: Only {len(clean)} clean candidates; "
              f"backfilling {needed} flagged candidates.", file=sys.stderr)

    # Ensure we have exactly top_n
    final_top = final_top[:args.top_n]

    # --- Print top-30 summary ---
    print(f"\n{'='*70}", file=sys.stderr)
    print(f"TOP 30 CANDIDATES", file=sys.stderr)
    print(f"{'='*70}", file=sys.stderr)
    header = f"{'ID':<15}{'Score':>8}  {'Signal':>7}  {'HP':>4}  {'Yrs':>5}  Title"
    print(header, file=sys.stderr)
    print("-" * 80, file=sys.stderr)
    for i, r in enumerate(final_top[:30], 1):
        hp_flag = "  HP" if r["is_honeypot"] else ""
        print(
            f"{r['candidate_id']:<15}{r['final_score']:>8.1f}  "
            f"{r['signal_score']:>7.1f}  {hp_flag:>4}  "
            f"{r['years_of_experience']:>5.1f}  "
            f"{r['current_title'][:50]}",
            file=sys.stderr
        )

    # --- Write submission CSV ---
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    # Normalise scores to [0.01, 1.00] range for submission
    max_score  = final_top[0]["final_score"]  if final_top else 1
    min_score  = final_top[-1]["final_score"] if final_top else 0
    score_range = max_score - min_score if max_score != min_score else 1

    # Pre-compute normalised scores for all candidates
    for row in final_top:
        row["_normalised"] = round(
            0.01 + 0.99 * (row["final_score"] - min_score) / score_range,
            4
        )

    # Final sort: normalised score desc, candidate_id asc on ties.
    # This matches the validator's exact tie-break rule — two candidates with
    # identical 4-decimal normalised scores must appear in candidate_id
    # ascending order.
    final_top.sort(key=lambda r: (-r["_normalised"], r["candidate_id"]))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        for rank, row in enumerate(final_top, 1):
            reasoning = build_reasoning(row)
            writer.writerow([
                row["candidate_id"],
                rank,
                row["_normalised"],
                reasoning,
            ])

    print(f"\n✓ Submission written: {args.out} ({len(final_top)} candidates)", file=sys.stderr)
    print(f"  Top score:    {final_top[0]['final_score']:.1f} → {final_top[0]['_normalised']:.4f}", file=sys.stderr)
    print(f"  Bottom score: {final_top[-1]['final_score']:.1f} → {final_top[-1]['_normalised']:.4f}", file=sys.stderr)



if __name__ == "__main__":
    main()
