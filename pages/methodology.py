import streamlit as st
import os

st.set_page_config(page_title="Methodology & Architecture", page_icon="📐", layout="wide")

# Inject Google Font and Clean Custom CSS with NO BLANK LINES inside the string to prevent raw text rendering
st.markdown("""<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"><style>html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }.block-container { padding-top: 2rem !important; }.stApp { background: #FAFAFA; color: #1E293B; }.sec-card { border-radius: 12px; padding: 24px 28px; margin-bottom: 24px; border-width: 1.5px; border-style: solid; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.02); }.sec-1 { background: #E0F2FE; border-color: #0284C7; color: #0369A1; }.sec-2 { background: #F1F5F9; border-color: #64748B; color: #334155; }.sec-3 { background: #D1FAE5; border-color: #059669; color: #065F46; }.sec-4 { background: #FEE2E2; border-color: #DC2626; color: #991B1B; }.sec-5 { background: #FFEDD5; border-color: #EA580C; color: #9A3412; }.sec-6 { background: #FEF9C3; border-color: #CA8A04; color: #854D0E; }.sec-7 { background: #FFFDE7; border-color: #FACC15; color: #A16207; }.sec-8 { background: #FEF08A; border-color: #EAB308; color: #854D0E; border-width: 3px; }.sec-9 { background: #F3E8FF; border-color: #9333EA; color: #6B21A8; }.sec-10 { background: #DBEAFE; border-color: #2563EB; color: #1E40AF; }.sec-11 { background: #EFF6FF; border-color: #3B82F6; color: #1E3A8A; }.sec-card h3 { font-size: 17px; font-weight: 700; margin: 0 0 14px 0; display: flex; align-items: center; gap: 8px; color: inherit; }.sec-card p, .sec-card li { font-size: 14.5px; line-height: 1.6; color: #334155; }.sec-card ul { margin-bottom: 12px; }code, pre { font-family: 'JetBrains Mono', monospace !important; background: rgba(255, 255, 255, 0.6); padding: 2px 6px; border-radius: 4px; font-size: 13.5px; color: #0F172A !important; font-weight: 500; }.formula-block { font-family: 'JetBrains Mono', monospace !important; background: rgba(255, 255, 255, 0.8) !important; padding: 16px; border-radius: 8px; font-size: 13.5px; color: #1E293B; line-height: 1.5; white-space: pre-wrap; border-left: 4px solid #EAB308; margin: 16px 0; }</style>""", unsafe_allow_html=True)

# Custom SVG Page Header
st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding-bottom:16px;
            border-bottom:2px solid #E2E8F0;margin-bottom:28px">
  <div style="background:#EEF2FF;border-radius:12px;padding:10px;display:flex">
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#4F46E5"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="9 11 12 14 22 4"/>
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
    </svg>
  </div>
  <div>
    <h1 style="margin:0;font-size:24px;font-weight:700;color:#0F172A;letter-spacing:-0.02em">
      Software Architecture & Methodology
    </h1>
    <p style="margin:2px 0 0;font-size:13px;color:#64748B">
      Full technical specification of the Redrob Candidate Ranker
    </p>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
This documentation details the 11 pipeline layers of the **Redrob Intelligent Candidate Discovery & Ranking** system, outlining all thresholds, weights, and logic gates implemented.
""")

# ── Architecture Diagram (Image) ──
st.markdown("###  System Architecture Flowchart")

image_paths = ["docs/architecture.png", "architecture.png"]
found_image = None
for path in image_paths:
    if os.path.exists(path):
        found_image = path
        break

if found_image:
    st.image(found_image, use_container_width=True, caption="Redrob Candidate Ranker Architecture Diagram")
else:
    st.markdown("""
    <div style="
        border: 2px dashed #CBD5E1;
        border-radius: 12px;
        padding: 40px 20px;
        text-align: center;
        background-color: #F8FAFC;
        margin-bottom: 24px;
    ">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 16px;">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
        </svg>
        <h4 style="margin: 0 0 8px 0; color: #475569; font-weight: 600;">Architecture Flowchart Placeholder</h4>
        <p style="margin: 0; font-size: 14px; color: #64748B; line-height: 1.5;">
            To display your diagram here, please save your software architecture flowchart image as:<br>
            <code>architecture.png</code> in the root directory, or under <code>docs/architecture.png</code>.
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── 1. Input Layer ────────────────────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-1">
  <h3>1. Input Layer</h3>
  <p>Responsible for loading the raw files into memory efficiently:</p>
  <ul>
    <li><strong>Source Files:</strong> Supports <code>candidates.jsonl</code>, <code>candidates.json</code>, or compressed <code>.jsonl.gz</code>.</li>
    <li><strong>Auto-Detection in <code>load_candidates()</code>:</strong> Peeks at the first non-whitespace character. If it is <code>[</code>, it parses the file as a single JSON array using <code>json.load()</code>. Otherwise, it streams line-by-line as a JSONL file.</li>
    <li><strong>Memory Efficiency:</strong> Streams individual rows as python generator structures to prevent memory spikes on large candidate pools.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 2. Text Extraction ────────────────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-2">
  <h3>2. Text Extraction</h3>
  <p>To avoid keyword-stuffing hacks in candidate resumes, text is parsed selectively:</p>
  <ul>
    <li><code>career_text_only()</code>: Extracts the <code>current_title</code>, <code>headline</code>, and all job titles and descriptions in <code>career_history</code>. <em>This is the primary signal source. It excludes the skills block to avoid keyword-stuffers.</em></li>
    <li><code>skills_txt</code>: Joins all elements from the <code>skills</code> block into a separate searchable string.</li>
    <li><code>all_text()</code>: Combines profile headers, summaries, career logs, and skills. Used as a secondary fallback.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 3. Domain Signal Scoring Engine ───────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-3">
  <h3>3. Domain Signal Scoring Engine</h3>
  <p>Applies compiled regular expressions to match unique terms against career text and skills text:</p>
  <ul>
    <li><strong>Strong Terms (weight per unique match):</strong>
      <ul>
        <li><code>ndcg</code> &rarr; <code>40</code> | <code>mrr</code> &rarr; <code>40</code></li>
        <li><code>search engineer</code>, <code>ranking engineer</code>, <code>relevance engineer</code>, <code>matching engineer</code>, <code>recommendation engineer</code>, <code>recommender engineer</code> &rarr; <code>35</code></li>
        <li><code>query understanding</code>, <code>search infrastructure</code>, <code>learning-to-rank</code> &rarr; <code>30</code></li>
        <li><code>personalization</code>, <code>collaborative filtering</code> &rarr; <code>25</code></li>
        <li><code>information retrieval</code>, <code>click-through rate</code>, <code>map@k</code> &rarr; <code>20</code></li>
      </ul>
    </li>
    <li><strong>Medium Terms:</strong>
      <ul>
        <li><code>bm25</code> &rarr; <code>15</code> | <code>elasticsearch</code>, <code>opensearch</code>, <code>qdrant</code>, <code>weaviate</code>, <code>milvus</code> &rarr; <code>12</code></li>
        <li><code>ranking</code>, <code>recommendation</code> &rarr; <code>10</code> | <code>recommender</code> &rarr; <code>8</code></li>
        <li><code>semantic search</code>, <code>vector search</code>, <code>vector database</code>, <code>search relevance</code>, <code>click-through</code> &rarr; <code>8</code></li>
      </ul>
    </li>
    <li><strong>Weak Terms:</strong>
      <ul>
        <li><code>retrieval</code> &rarr; <code>5</code> | <code>matching system</code>, <code>matching engine</code> &rarr; <code>4</code></li>
        <li><code>embeddings</code>, <code>pinecone</code>, <code>faiss</code>, <code>vector db</code> &rarr; <code>3</code></li>
      </ul>
    </li>
  </ul>
  <p><strong>Scoring Rules:</strong></p>
  <ul>
    <li>Deduplicated by label (each term matches only ONCE).</li>
    <li><code>career_signal</code> = Sum of unique matches inside <code>career_text_only()</code>.</li>
    <li><code>skills_signal_raw</code> = <code>(strong_skills * 0.5) + (medium_skills * 0.4) + (weak_skills * 0.2)</code>.</li>
    <li><code>skills_signal</code> = <code>min(skills_signal_raw, 60)</code> (hard cap to neutralize keyword-stuffers).</li>
    <li><code>signal_score</code> = <code>career_signal + skills_signal</code>.</li>
    <li><code>has_signal = signal_score > 0</code> gates all downstream behavioral bonuses.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 4. Hard Disqualifiers & Honeypots ──────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-4">
  <h3>4. Hard Disqualifiers / Honeypot Checks</h3>
  <p>Runs six parallel integrity checkers. Any match flags the candidate as a honeypot, applying <code>honeypot_penalty = 2000</code>:</p>
  <ol>
    <li><strong>Duplicate Achievement Check (<code>check_self_contradicting_duplicate</code>):</strong> Flags profiles where identical high-signal paragraphs appear verbatim across different jobs (Zomato vs Google). Generic filler text is skipped.</li>
    <li><strong>Anachronistic Certifications (<code>check_anachronistic_cert</code>):</strong> Flags cert years that predate public releases of libraries:
      <ul>
        <li><code>langchain</code> / <code>llamaindex</code> &rarr; 2022</li>
        <li><code>gpt-4</code> / <code>chatgpt</code> / <code>stable diffusion</code> &rarr; 2022-2023</li>
        <li><code>mistral</code> / <code>llama 2</code> / <code>llama2</code> &rarr; 2023</li>
        <li><code>qdrant</code> / <code>pinecone</code> &rarr; 2021 | <code>weaviate</code> &rarr; 2019</li>
      </ul>
    </li>
    <li><strong>Anachronistic Institutions (<code>check_anachronistic_institution</code>):</strong> Flags enrollment start dates prior to university founding years (e.g., enrolled at IIT Hyderabad prior to its 2008 founding).</li>
    <li><strong>Experience Inflation (<code>check_experience_inflation</code>):</strong>
      <ul>
        <li>Compares <code>profile.years_of_experience</code> against actual sum of job durations (months / 12).</li>
        <li>Gap &gt; 7 years &rarr; <code>hard_honeypot</code> &rarr; Penalty: <code>2000</code></li>
        <li>Gap 4–7 years &rarr; <code>strong inflation</code> &rarr; Soft Penalty: <code>150</code></li>
        <li>Gap 2–4 years &rarr; <code>moderate inflation</code> &rarr; Soft Penalty: <code>60</code></li>
        <li>Also flags if the candidate summary text claims experience that contradicts the profile field by &gt; 2 years.</li>
      </ul>
    </li>
    <li><strong>Degree-Institution Mismatch (<code>check_degree_mismatch</code>):</strong> Indian degrees like B.Tech/M.Tech claimed at major US universities (Stanford, MIT, Harvard, CMU, etc.) &rarr; Soft Penalty: <code>30</code></li>
    <li><strong>Degree Duration Anomalies (<code>check_degree_duration_anomaly</code>):</strong> Degree duration outside standard rules (B.Tech/B.E. = 3–5 yrs, M.Tech/M.E./MBA = 1–3 yrs, PhD = 3–8 yrs) &rarr; Soft Penalty: <code>20</code></li>
  </ol>
  <p><strong>Additional Check:</strong> <code>check_duration_contradiction()</code> flags if career description claims a duration (e.g. "for 3 years") that contradicts the job's month metadata by &gt; 50% &rarr; Soft Penalty: <code>25</code>.</p>
</div>
""", unsafe_allow_html=True)

# ── 5. Behavioral & Engagement Signals ────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-5">
  <h3>5. Behavioral & Engagement Signals</h3>
  <p>To avoid scoring noise, engagement bonuses are <strong>gated on <code>has_signal = True</code></strong>:</p>
  <ul>
    <li><strong>Skill Assessment Bonus:</strong>
      <div class="formula-block">assessment_bonus = (assessment_avg * 0.4) + (assessment_max * 0.2) + (assessment_count * 4)</div>
      If no assessments are taken: <code>zero_assessment_penalty = -30</code>.
    </li>
    <li><strong>Recruiter Engagement Bonus:</strong>
      <div class="formula-block">recruiter_bonus = (saved_by_recruiters_30d * 1.2) + (recruiter_response_rate * 25) + (interview_completion_rate * 15) + (applications_submitted_30d * 0.5)</div>
    </li>
    <li><strong>GitHub Activity:</strong>
      <div class="formula-block">github_bonus = github_activity_score * 0.3 (only if github_score >= 0)</div>
    </li>
    <li><strong>Availability (Always Applied):</strong>
      <ul>
        <li><code>open_to_work = True</code> &rarr; <code>+20</code> | <code>open_to_work = False</code> &rarr; <code>-15</code></li>
        <li>Last active &gt; 180 days &rarr; <code>-40</code> | Last active &gt; 90 days &rarr; <code>-20</code></li>
      </ul>
    </li>
    <li><strong>Notice Period Alignment:</strong>
      <ul>
        <li>Notice &le; 30 days &rarr; <code>+10</code> | Notice &gt; 60 days &rarr; <code>-10</code></li>
      </ul>
    </li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 6. Experience Fit ─────────────────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-6">
  <h3>6. Experience Fit</h3>
  <p>Evaluates experience years listed in <code>profile.years_of_experience</code> against target JD:</p>
  <ul>
    <li><strong>5–9 years:</strong> <code>+20</code> (sweet spot for Senior AI candidate)</li>
    <li><strong>4–12 years:</strong> <code>+10</code> (acceptable buffer)</li>
    <li><strong>&lt; 3 years:</strong> <code>-20</code> (too junior for senior role)</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 7. Additional Soft Signals ────────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-7">
  <h3>7. Additional Soft Signals</h3>
  <ul>
    <li><strong>Education Tiering:</strong> <code>tier_1</code> school &rarr; <code>+8</code> | <code>tier_2</code> school &rarr; <code>+4</code> (max bonus per candidate; non-cumulative).</li>
    <li><strong>Consulting-Only Penalty:</strong> Candidates whose career history contains only firms on our consulting blacklist (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, HCL, etc.) &rarr; <code>-300</code>.</li>
    <li><strong>Non-Tech Title Penalty:</strong> Current title matches non-engineering fields (marketing manager, HR manager, accountant, civil engineer, etc.) AND <code>career_signal < 30</code> &rarr; <code>-500</code>.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 8. Composite Score Formula ────────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-8">
  <h3>8. Composite Score Formula</h3>
  <p>The total candidate score is calculated as a single composite formula:</p>
  <div class="formula-block">final_score = (
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
    - consulting_penalty            (300)
    - honeypot_penalty              (2000)
    - degree_mismatch_penalty       (30)
    - deg_duration_anomaly_penalty  (20)
    - dur_contradiction_penalty     (25)
    - exp_inflation_penalty         (60 / 150 / 2000)
    - non_tech_title_penalty        (500)
)</div>
</div>
""", unsafe_allow_html=True)

# ── 9. Pass 2: Sibling Deduplication ──────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-9">
  <h3>9. Pass 2: Cross-Candidate Deduplication</h3>
  <p>To remove templated/AI-generated profiles from taking multiple top spots:</p>
  <ul>
    <li><code>find_near_duplicate_siblings()</code> builds an inverted index of descriptions (> 50 characters).</li>
    <li>If 2+ candidates share even <strong>1</strong> identical role description, they are flagged as "template twins".</li>
    <li>The candidate with the <strong>lower or tied final score</strong> receives a <code>-50</code> penalty.</li>
    <li>The candidates are then re-sorted by <code>(-final_score, candidate_id)</code>.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 10. Selection & Normalization ─────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-10">
  <h3>10. Selection & Normalization</h3>
  <ul>
    <li>Splits the candidates into a <code>clean</code> pool (no honeypot checks triggered) and a <code>flagged</code> pool.</li>
    <li>Selects the top 100 clean candidates. If clean candidates are &lt; 100, the remaining slots are backfilled from the flagged pool sorted by score.</li>
    <li>Normalized scores to the <code>[0.01, 1.00]</code> range:
      <div class="formula-block">normalized = 0.01 + 0.99 * (final_score - min_score) / (max_score - min_score)</div>
    </li>
    <li>Sorts the output by <code>(-normalized_score, candidate_id ascending)</code> for deterministic tie-breaking.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

# ── 11. Output Files ──────────────────────────────────────────────────────────
st.markdown("""
<div class="sec-card sec-11">
  <h3>11. Output Files</h3>
  <ul>
    <li><strong><code>submission.csv</code>:</strong> Contains exactly the top 100 candidates with fields: <code>candidate_id</code>, <code>rank</code>, <code>score</code> (normalized to 4 decimal places), and a generated <code>reasoning</code> string.
      <ul>
        <li><em>Reasoning format:</em> <code>{current_title} ({years_exp} yrs); strong signals: {hits}; {assessment_count} assessments; open_to_work; resp={recruiter_response}</code>.</li>
      </ul>
    </li>
    <li><strong><code>full_scores.csv</code>:</strong> Contains the top 2000 candidates with all diagnostic columns for verification and testing.</li>
  </ul>
</div>
""", unsafe_allow_html=True)
