"""
app.py — Redrob Candidate Ranker — Streamlit Sandbox

Sandbox demo for the Redrob Intelligent Candidate Discovery & Ranking challenge.
Upload a candidates.jsonl file, get a ranked shortlist back.
"""

import streamlit as st
import pandas as pd
import json
import io
import csv
import sys
import os

# Add src/ to path so we can import rank.py logic
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from rank import (
    compute_candidate_score,
    find_near_duplicate_siblings,
    build_reasoning,
    load_candidates,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Redrob Candidate Ranker",
    layout="wide",
)

# Inject Google Font and clean CSS (safely avoiding overriding icon/toggle arrow fonts)
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* Safe Typography inheritance */
    html, body, [class*="css-"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* Push content up by reducing top padding of Streamlit's container */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Clean layout background */
    .stApp {
        background-color: #FAFAFA;
        color: #1E293B;
    }
    
    /* Clean custom button design (standard buttons + uploader browse button) */
    .stButton>button, [data-testid="stFileUploader"] button {
        background-color: #4F46E5 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover, [data-testid="stFileUploader"] button:hover {
        background-color: #4338CA !important;
        box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2) !important;
        border: none !important;
    }
    /* Force nested children inside the upload button to be white text */
    [data-testid="stFileUploader"] button * {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Custom SVG Header (lucide search/compass icon styled, more compact to push content up)
st.markdown("""
<div style="
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 0;
    margin-bottom: 16px;
    border-bottom: 1px solid #E2E8F0;
">
    <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon>
    </svg>
    <div>
        <h1 style="
            font-size: 26px;
            font-weight: 700;
            color: #0F172A;
            margin: 0;
            letter-spacing: -0.02em;
        ">Redrob Candidate Ranker</h1>
        <p style="
            font-size: 13.5px;
            color: #64748B;
            margin: 2px 0 0 0;
        ">Intelligent Talent Matching Platform • Senior AI Engineer</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── JD summary ───────────────────────────────────────────────────────────────
with st.expander("Job Description & Evaluation Criteria", expanded=False):
    st.markdown("""
**Role:** Senior AI Engineer — Search, Retrieval & Ranking  
**Company:** Redrob AI  

**What we're looking for:**
- 5–9 years experience, with 4–5 in applied ML/AI at **product companies**
- Has personally **shipped** search, ranking, retrieval or recommendation systems in production
- Hands-on: still writing code, not purely strategic/management
- Can speak with depth about: hybrid vs dense retrieval, offline vs online eval, learning-to-rank
- Available now or soon

**Hard disqualifiers:**
- 100% consulting career (TCS/Infosys/Wipro/Accenture etc.) with no product company exposure
- Marketing/non-engineering role with AI keywords pasted into skills
- Pure CV/speech/robotics with no NLP/IR substance
- Anachronistic certifications (e.g. LangChain cert dated before 2022)
    """)

# ── File upload ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" x2="12" y1="3" y2="15"></line>
    </svg>
    <span style="font-size: 18px; font-weight: 600; color: #1E293B;">Upload Candidate Dataset</span>
</div>
""", unsafe_allow_html=True)

# File upload limit is extended to 1GB (1024MB) via .streamlit/config.toml
uploaded = st.file_uploader(
    "Choose candidates.jsonl or candidates.json",
    type=["jsonl", "json", "gz"],
    help="Standard Redrob candidate JSONL or JSON format"
)

top_n = st.slider("How many top candidates to show?", 10, 100, 50)

# ── Run ranking ───────────────────────────────────────────────────────────────
if uploaded is not None:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
        <span style="font-size: 18px; font-weight: 600; color: #1E293B;">Ranking Summary</span>
    </div>
    """, unsafe_allow_html=True)

    progress = st.progress(0, text="Loading candidates...")

    # Parse uploaded file
    raw_bytes = uploaded.read()
    candidates_raw = []

    try:
        if uploaded.name.endswith(".gz"):
            import gzip
            f = gzip.open(io.BytesIO(raw_bytes), "rt", encoding="utf-8")
        else:
            f = io.StringIO(raw_bytes.decode("utf-8"))

        with f:
            # Peek first character to check if it's a JSON array
            first_char = ""
            for char in f.read(100):  # read up to 100 chars to skip whitespace
                if char.strip():
                    first_char = char
                    break
            
            f.seek(0)
            if first_char == "[":
                # JSON array
                data = json.load(f)
                if isinstance(data, list):
                    candidates_raw = data
                elif isinstance(data, dict):
                    candidates_raw = [data]
            else:
                # JSONL
                for line in f:
                    line = line.strip()
                    if line:
                        candidates_raw.append(json.loads(line))
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        st.stop()

    total = len(candidates_raw)
    st.markdown(f"""
    <div style="font-size: 14px; color: #475569; margin-bottom: 12px;">
        Loaded <strong>{total:,}</strong> candidate profiles.
    </div>
    """, unsafe_allow_html=True)

    # Score each candidate
    results = []
    candidate_desc_sets = {}

    for i, c in enumerate(candidates_raw):
        if i % max(1, total // 20) == 0:
            progress.progress(i / total, text=f"Scoring candidate {i+1:,} of {total:,}...")

        row = compute_candidate_score(c)
        if row["signal_score"] > 0 or row["final_score"] > 50:
            results.append(row)
            candidate_desc_sets[row["candidate_id"]] = frozenset(
                r.get("description", "") or ""
                for r in c.get("career_history", [])
            )

    progress.progress(0.85, text="Checking for template duplicates...")

    # Sibling dedup
    siblings_map = find_near_duplicate_siblings(candidate_desc_sets)
    results.sort(key=lambda r: -r["final_score"])
    score_by_id = {r["candidate_id"]: r["final_score"] for r in results}

    for cid, sibling_ids in siblings_map.items():
        my_score = score_by_id.get(cid)
        if my_score is None:
            continue
        sibling_scores = [score_by_id[s] for s in sibling_ids if s in score_by_id]
        if sibling_scores and my_score <= max(sibling_scores):
            for r in results:
                if r["candidate_id"] == cid:
                    r["final_score"] = round(r["final_score"] - 50, 2)
                    break

    results.sort(key=lambda r: -r["final_score"])

    # Separate clean from honeypots
    clean = [r for r in results if not r["is_honeypot"]]
    honeypots = [r for r in results if r["is_honeypot"]]

    progress.progress(1.0, text="Processing complete")
    
    # Success banner (Lucide check circle icon)
    st.markdown(f"""
    <div style="
        background-color: #ECFDF5;
        border: 1px solid #A7F3D0;
        border-radius: 8px;
        padding: 14px 16px;
        color: #065F46;
        font-size: 14.5px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 20px;
    ">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
        <span>Successfully processed dataset. Identified <strong>{len(clean)}</strong> clean candidates with relevant domain signals. <strong>{len(honeypots)}</strong> honeypots were filtered out.</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Results table ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="8" x2="21" y1="6" y2="6"></line>
            <line x1="8" x2="21" y1="12" y2="12"></line>
            <line x1="8" x2="21" y1="18" y2="18"></line>
            <line x1="3" x2="3.01" y1="6" y2="6"></line>
            <line x1="3" x2="3.01" y1="12" y2="12"></line>
            <line x1="3" x2="3.01" y1="18" y2="18"></line>
        </svg>
        <span style="font-size: 18px; font-weight: 600; color: #1E293B;">Top {min(top_n, len(clean))} Candidates</span>
    </div>
    """, unsafe_allow_html=True)

    # Explanation for candidate count (Addresses "Why only 11 candidates?")
    if len(clean) < top_n:
        st.markdown(f"""
        <div style="
            background-color: #EFF6FF;
            border: 1px solid #BFDBFE;
            border-radius: 8px;
            padding: 14px 16px;
            color: #1E40AF;
            font-size: 14px;
            margin-bottom: 20px;
            line-height: 1.5;
        ">
            <div style="display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 6px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" x2="12" y1="16" y2="12"></line>
                    <line x1="12" x2="12.01" y1="8" y2="8"></line>
                </svg>
                Why are only {len(clean)} candidates shown?
            </div>
            The uploaded dataset contains <strong>{total}</strong> candidates. Our ranking system filters out profiles that do not match the core requirements for the Senior AI Engineer role (e.g., candidates with no search/ranking experience, consulting-only backgrounds, or marketing profiles), leaving <strong>{len(clean)}</strong> qualified candidates.
        </div>
        """, unsafe_allow_html=True)

    final = clean[:top_n]

    # Normalise scores for display
    if final:
        max_s = final[0]["final_score"]
        min_s = final[-1]["final_score"]
        score_range = max_s - min_s if max_s != min_s else 1

    display_rows = []
    for rank, row in enumerate(final, 1):
        normalised = round(0.01 + 0.99 * (row["final_score"] - min_s) / score_range, 4) if final else 0
        reasoning = build_reasoning(row)
        display_rows.append({
            "Rank": rank,
            "Candidate ID": row["candidate_id"],
            "Score": normalised,
            "Title": row["current_title"],
            "Company": row["current_company"],
            "Yrs Exp": row["years_of_experience"],
            "Strong Signals": row["strong_hits"] if row["strong_hits"] else "None",
            "Assessments": f"{row['assessment_count']} (avg {row['assessment_avg']:.0f})" if row['assessment_count'] > 0 else "None",
            "Open to Work": "Active" if row["open_to_work"] else "Passive",
            "Reasoning": reasoning,
        })

    df = pd.DataFrame(display_rows)
    st.dataframe(df, width='stretch', height=600)

    # ── Honeypot summary ──────────────────────────────────────────────────────
    if honeypots:
        st.markdown(f"""
        <div style="
            background-color: #FEF2F2;
            border: 1px solid #FCA5A5;
            border-radius: 8px;
            padding: 14px 16px;
            color: #991B1B;
            font-size: 14px;
            margin-bottom: 20px;
            line-height: 1.5;
        ">
            <div style="display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 4px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                    <line x1="12" x2="12" y1="9" y2="13"></line>
                    <line x1="12" x2="12.01" y1="17" y2="17"></line>
                </svg>
                Honeypot Profiles Detected
            </div>
            Our integrity checks flagged <strong>{len(honeypots)}</strong> profile(s) with structural anomalies, such as duplicate role achievements across different companies or impossible certification years. These have been excluded from the ranking table.
        </div>
        """, unsafe_allow_html=True)

        with st.expander("View Flagged Profiles (Excluded from Ranking)", expanded=False):
            hp_rows = []
            for r in honeypots[:20]:
                hp_rows.append({
                    "Candidate ID": r["candidate_id"],
                    "Title": r["current_title"],
                    "Company": r["current_company"],
                    "Reason": r["honeypot_reason"][:100],
                })
            st.dataframe(pd.DataFrame(hp_rows), width='stretch')

    # ── Download ──────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" x2="12" y1="15" y2="3"></line>
        </svg>
        <span style="font-size: 18px; font-weight: 600; color: #1E293B;">Export Results</span>
    </div>
    """, unsafe_allow_html=True)

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for rank, row in enumerate(final, 1):
        normalised = round(0.01 + 0.99 * (row["final_score"] - min_s) / score_range, 4) if final else 0
        writer.writerow([row["candidate_id"], rank, normalised, build_reasoning(row)])

    st.download_button(
        label="Download Shortlist (submission.csv)",
        data=csv_buf.getvalue(),
        file_name="submission.csv",
        mime="text/csv",
    )

    # ── Stats ─────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 12px 0;">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
        <span style="font-size: 18px; font-weight: 600; color: #1E293B;">Coverage Metrics</span>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total candidates", f"{total:,}")
    col2.metric("With domain signal", f"{len(results):,}")
    col3.metric("Honeypots caught", f"{len(honeypots)}")
    col4.metric("Clean shortlist", f"{len(clean):,}")

else:
    st.markdown("""
    <div style="
        background-color: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-radius: 8px;
        padding: 16px 20px;
        color: #1E40AF;
        font-size: 14.5px;
        line-height: 1.5;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" x2="12" y1="16" y2="12"></line>
            <line x1="12" x2="12.01" y1="8" y2="8"></line>
        </svg>
        <span>To begin, please upload a candidate profile file in the form above.</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px 20px;
        background-color: #FFFFFF;
        margin-top: 12px;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 11 12 14 22 4"></polyline>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        <span style="font-size: 14px; color: #475569;">
            Looking for how candidates are evaluated? Expand the sidebar and open the <strong>Methodology & Architecture</strong> page for the full 11-layer technical specification.
        </span>
    </div>
    """, unsafe_allow_html=True)

