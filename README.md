# 🔍 Redrob Intelligent Candidate Ranker

A candidate ranking and talent discovery system built for the India Runs Hackathon – Data & AI Challenge. The platform analyzes large-scale candidate datasets and identifies high-potential Senior AI/Search Engineers by combining domain-specific relevance signals, behavioral hiring signals, and deterministic integrity checks.

Unlike traditional keyword matching systems, the ranker evaluates candidates through a gated scoring engine that prioritizes demonstrated search, ranking, recommendation, and retrieval expertise. The system incorporates recruiter engagement signals, verified skill assessments, profile quality indicators, activity metrics, and hiring-readiness features to produce explainable candidate rankings.

To improve shortlist quality, the platform includes multiple integrity filters designed to detect synthetic or misleading profiles. These checks identify duplicate achievements across career histories, experience inflation, anachronistic certifications, institution-year inconsistencies, degree mismatches, and other logical contradictions commonly found in generated resumes. A sibling-deduplication mechanism further reduces redundancy by identifying near-identical profile templates across candidates.

The ranking pipeline is designed to operate efficiently on large candidate pools while maintaining transparency in scoring decisions. Each shortlisted candidate receives a traceable score breakdown, making the ranking process interpretable for recruiters and hiring teams.

---

## 🤖 AI Tools & Engineering Declaration
* **AI Tool Utilized**: **Claude AI** was utilized in the initial stage to analyze, explain, and unpack the 23 behavioral signals in an explainable way.
* **Engineering Effort**: Following the initial analysis, **13+ hours of rigorous manual development, data calibration, and scripting** were spent to sync with the project goals, code the search signal weights, construct deterministic integrity checks, and build the custom interactive dashboard.

---

## 📂 Project Structure
Below is the directory structure focusing only on the files actively used for the ranking and web application process:

```text
Redrob/
├── .streamlit/
│   └── config.toml         # Configures 1GB file upload limit and locks Light Theme
├── src/
│   ├── rank.py             # Core candidate scoring, honeypot filtering, and ranking logic
│   └── __init__.py         # Module initialization
├── app.py                  # Main Streamlit web application & user interface
├── requirements.txt        # Python package dependencies (streamlit, pandas)
└── README.md               # Project documentation (this file)
```

---

## 📋 Job Description & Evaluation Criteria
The system ranks candidates against the **Senior AI Engineer — Founding Team** role for Redrob AI:
* **The Sweet Spot**: 5–9 years of total experience, with 4–5 years specifically in applied ML/AI at **product companies** (shipping own software at scale).
* **Core Technical Depth**: Production experience with embedding-based retrieval, hybrid search infrastructure (e.g., FAISS, Elasticsearch, Pinecone), and evaluation metrics (NDCG, MRR, MAP).
* **Hard Disqualifiers (Filtered Deterministically)**:
  * Candidates who spent their entire careers at **consulting/services firms** (e.g., TCS, Infosys, Wipro, Accenture) with zero product exposure.
  * Candidates in **marketing or non-tech roles** who have stuffed AI keywords into their profiles.
  * Candidates with **anachronistic profiles** (impossible certification years, degree-institution mismatches) classified as honeypots.
  * Candidates who are purely managers and have **not written code in the last 18 months**.

---

## 📊 Behavioral Signals (The 23 Signals)
In a talent marketplace, static profiles can be misleading. Candidates generate behavioral signals that indicate their availability and verified skills. 

Our ranker parses and handles these **23 behavioral signals** as follows:

| # | Signal Name | Range / Type | Integration & Weighting Logic |
|---|---|---|---|
| **1** | `profile_completeness_score` | `0 - 100` | Used as quality indicator; low completeness downweights score. |
| **2** | `signup_date` | `date string` | Metadata for account age. |
| **3** | `last_active_date` | `date string` | Evaluated relative to today. **Last active > 90 days** incurs a **20-point penalty**; **> 180 days** incurs a **40-point penalty** (indicates unavailability). |
| **4** | `open_to_work_flag` | `boolean` | **+20 point bonus** if `True`. **-15 point penalty** if `False` (deprioritizes passive candidates). |
| **5** | `profile_views_received_30d`| `integer >= 0` | Metrics tracking overall profile interest. |
| **6** | `applications_submitted_30d`| `integer >= 0` | Combined with recruiter saves for active job seeker bonus (**+0.5 points per application**). |
| **7** | `recruiter_response_rate` | `0.0 - 1.0` | **Gated Bonus**: Up to **+25 points** (only if candidate has matching domain search signals). |
| **8** | `avg_response_time_hours` | `number >= 0` | Measure of candidate responsiveness. |
| **9** | `skill_assessment_scores` | `dict[str, 0-100]`| **Verified Assessments**: Zero assessments taken triggers a **-30 point penalty**. Verified scores grant a gated bonus: `(avg * 0.4) + (max * 0.2) + (count * 4)` to reward proven skills. |
| **10**| `connection_count` | `integer >= 0` | Measure of professional network size. |
| **11**| `endorsements_received` | `integer >= 0` | Metric indicating peer validation. |
| **12**| `notice_period_days` | `0 - 180` | **Notice Period Alignment**: **<= 30 days** grants a **+10 point bonus**; **> 60 days** triggers a **-10 point penalty** (preferring quick onboarding). |
| **13**| `expected_salary_range_inr` | `min/max LPA` | Used to evaluate alignment with standard hiring budget. |
| **14**| `preferred_work_mode` | `work mode` | Preference matching (e.g., hybrid/flexible matching our Pune/Noida offices). |
| **15**| `willing_to_relocate` | `boolean` | Factor for relocation to physical offices. |
| **16**| `github_activity_score` | `-1 to 100` | Gated open-source engagement bonus (**+0.3 points per score point**, maximum 30). |
| **17**| `search_appearance_30d` | `integer >= 0` | Platform search visibility metrics. |
| **18**| `saved_by_recruiters_30d` | `integer >= 0` | **Gated Bonus**: **+1.2 points per save** (captures recruiter interest). |
| **19**| `interview_completion_rate` | `0.0 - 1.0` | **Gated Bonus**: Up to **+15 points** (indicates follow-through). |
| **20**| `offer_acceptance_rate` | `-1 to 1.0` | Measure of placement reliability. |
| **21**| `verified_email` | `boolean` | Verification checklist. |
| **22**| `verified_phone` | `boolean` | Verification checklist. |
| **23**| `linkedin_connected` | `boolean` | Verification checklist. |

---

## ⚡ Scoring Engine & Integrity Filters
To prevent keyword-stuffers and honeypots from polluting the pipeline, the ranker operates on a strict **Gated Composite Scoring Engine**:

### 1. Signal Detection Calibration
* **Career Text scoring**: A raw keyword scan is performed over descriptions and titles, but split into calibrated tiers:
  * **Strong (40 pts)**: Highly specific terms like *NDCG*, *MRR*, *Learning-to-Rank*, or titles like *Search Engineer* (found in <1% of the candidate pool).
  * **Medium (12 pts)**: Supporting infrastructure terms like *BM25*, *Elasticsearch*, *Qdrant*, *Milvus*.
  * **Weak (3 pts)**: Diluted terms like *embeddings* or *FAISS* (found in ~5% of pool).
* **Skills Cap**: Direct skills lists are capped at **60 points** to prevent candidates from stuffing keywords to bypass the ranker.

### 2. Gated Bonuses
Recruiter engagement bonuses and skill assessment bonuses **only apply if the candidate has a base domain signal score > 0**. Keyword-stuffers with zero domain search relevance cannot bypass the filters via platform metrics.

### 3. Integrity Check Engine (Honeypot Elimination)
Deterministic rules apply a severe penalty (`-2000 points`) to instantly exclude honeypots from the ranking list:
* **Duplicate Achievements**: Identifies duplicate paragraphs/achievements copy-pasted across different roles in a single career history.
* **Anachronistic Certifications**: Flags certificates for technologies claimed before they were invented (e.g., claiming a LangChain certification in 2021).
* **Anachronistic Institutions**: Flags enrollment years that predate the founding of the institution (e.g., enrolling in IIT Hyderabad before its 2008 founding).
* **Experience Inflation**: Cross-references `profile.years_of_experience` against actual `duration_months` in the career history. A gap of **> 7 years** triggers an automatic honeypot flag.
* **Degree Mismatches**: Flags invalid combinations like a B.Tech degree at a US institution (e.g., Stanford).

### 4. Cross-Candidate Template Twins (Sibling Deduplication)
Calculates if different candidates share identical career history descriptions (indicating templated, synthetic resume generators). The lower-scoring duplicate is penalized **50 points** to protect top-100 slots from redundancy.

---

## 🚀 How to Run the App
Follow these steps to launch the interactive application locally:

### 1. Install Dependencies
Ensure you have Python installed, then run:
```bash
pip install -r requirements.txt
```

### 2. Run the Streamlit Application
Launch the application server with:
```bash
streamlit run app.py
```
This opens the browser automatically to `http://localhost:8501`. 

### 3. Features of the UI
* **1GB Upload Capacity**: Configured to handle massive datasets (e.g., up to 1GB `.json`, `.jsonl`, or `.gz` files).
* **Clean Light Theme**: Locked in Light Theme for consistent readability.
* **Filtering Summaries**: Displays why candidates were excluded, charts signal distributions, and catches honeypots.
* **Export Shortlists**: Download the top shortlisted candidates directly to a formatted `submission.csv` containing the final ranking and automated logical reasoning.
