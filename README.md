# Boutiqaat Influencer / Boutique Candidate Scoring

A small Python prototype that evaluates an Instagram or TikTok creator as a potential Boutiqaat Boutique owner.

The system combines deterministic business rules with model-assisted interpretation and produces:

- A fit score out of 100
- The signals driving the score
- An `ONBOARD`, `HOLD`, `PASS`, or `MANUAL REVIEW` recommendation
- JSON and Markdown reports
- A simple browser interface for non-technical users

## Quick start

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure a local `.env` file from `.env.example`:

```text
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_REASONING_MODEL=gemini-3.6-flash
QWEN_LOCAL_ENABLED=false
```

Run the browser interface:

```bash
python app.py
```

Open `http://127.0.0.1:5000` and select a candidate.

Run the CLI for one candidate:

```bash
python main.py --account-id HQ-101-KW --with-models --output-dir outputs
```

The reports are written to:

```text
outputs/<account_id>.json
outputs/<account_id>.md
```

## Architecture

```text
raw_data.json
      ↓
Candidate loading and identifier anonymization
      ↓
Deterministic preprocessing
      ↓
Gemini Flash-Lite post and brand interpretation
      ↓
Weighted scoring and hard-rule decisions
      ↓
Gemini 3.6 Flash final explanation
      ↓
JSON, Markdown, and browser output
```

The score and decision are calculated in Python. The models classify content and explain the evidence; they cannot override the deterministic result.

## Data flow and pipeline stages

The pipeline processes one selected candidate at a time:

```text
1. Load candidate
   raw_data.json + account_id
        ↓
2. Anonymize
   Remove account_id, username, and original post IDs from analytical payloads
        ↓
3. Preprocess
   Calculate GCC, reachable audience, engagement, ratios, and commercial rate
        ↓
4. Apply hard rules
   Private account, low GCC audience, and anomaly checks
        ↓
5. Interpret content
   Gemini Flash-Lite extracts commercial and product signals from each post
        ↓
6. Classify brands
   Gemini Flash-Lite assesses brand category, prestige tier, and catalog fit
        ↓
7. Score
   Python aggregates deterministic and model-derived features
        ↓
8. Decide
   ONBOARD, HOLD, PASS, or MANUAL REVIEW
        ↓
9. Explain
   Gemini 3.6 Flash explains the existing score and trade-offs
        ↓
10. Present and save
    Browser page + JSON report + Markdown report + compact log
```

### When each part is added

| Stage | Added by | Main output |
|---|---|---|
| Candidate loading | Python | One validated candidate |
| Anonymization | Python | Safe analytical payload |
| Preprocessing | Python | GCC, engagement, ratio, and commercial metrics |
| Hard-rule filtering | Python | Early `PASS` or `MANUAL REVIEW` flags |
| Post interpretation | Gemini Flash-Lite or optional local Qwen | Structured post signals |
| Brand classification | Gemini Flash-Lite | Brand and catalog-fit signals |
| Weighted scoring | Python | Score breakdown and final score |
| Decision assignment | Python | `ONBOARD`, `HOLD`, `PASS`, or `MANUAL REVIEW` |
| Final explanation | Gemini 3.6 Flash | Manager-readable reasoning |
| Reporting and UI | Python, Flask, HTML, CSS | Browser output and saved reports |

Hard rules are evaluated before the weighted score. The score is calculated before the final explanation. The final explanation is never allowed to modify the score or decision.

## Scoring logic

### Hard rules

These rules are applied before the weighted score:

```text
Private account              → MANUAL REVIEW
GCC audience below 45%       → PASS
Detected anomaly             → MANUAL REVIEW
```

The GCC audience percentage is the combined audience share from:

```text
Kuwait, Saudi Arabia, UAE, Qatar, Bahrain, Oman
```

The prototype also calculates:

```text
GCC reachable audience = followers × GCC audience percentage
Engagement rate         = (average likes + average comments) / followers
Likes/comments ratio    = average likes / average comments
Commercial content rate = commercial posts / total posts
```

### Weighted score

Candidates that pass the hard rules are evaluated using:

| Dimension | Weight |
|---|---:|
| Audience commercial viability | 30% |
| Commercialization and intent | 25% |
| Category and brand alignment | 25% |
| Content quality and consistency | 20% |

Decision thresholds:

```text
75–100 → ONBOARD
60–74  → HOLD
0–59   → PASS
```

If model evidence is unavailable, the system returns `MANUAL REVIEW` rather than making a confident automated recommendation from incomplete evidence.

## Model responsibilities

### Gemini Flash-Lite

Used for the current laptop implementation because the laptop cannot practically load Qwen2.5-14B locally.

It classifies:

- Commercial intent
- Calls to action
- Discount codes and restock signals
- Product reviews, unboxings, and education
- Brand category and prestige tier
- Boutiqaat catalog fit

### Qwen2.5-14B-Instruct

Qwen remains the intended local model for caption interpretation when suitable hardware is available. Enable it with:

```text
QWEN_LOCAL_ENABLED=true
```

The model is loaded lazily through Transformers. It is disabled by default on the current laptop.

### Gemini 3.6 Flash

Used for the final explanation because this step must reason across the score, anomalies, commercial signals, category fit, trade-offs, and limitations.

It explains the deterministic decision but cannot change it.

## Data and leakage protection

The mock identifiers contain outcome-like labels such as `BOT`, `POD-SUSPECT`, and `HIGH-CONVERSION`.

Therefore:

- `account_id` and `username` are excluded from scoring and model prompts.
- Post IDs are anonymized before model calls.
- Original identity is retained only for display and report filenames.
- Tests verify that changing identifiers does not change the score or recommendation.

Brand tags are treated as brand associations, not proof of paid collaborations.

## Known limitations

The mock dataset does not contain:

- Sponsorship or paid-partnership labels
- Attributed orders, revenue, or conversion outcomes
- Post-level reach, views, likes, comments, shares, or saves
- Historical follower counts

Therefore:

- Verified collaboration rate cannot be calculated.
- True post-performance volatility cannot be calculated.
- Historical profile-growth volatility cannot be calculated.
- The score is a transparent prototype rubric, not a trained outcome-prediction model.

These limitations are reported rather than hidden.

## Testing

Run all tests with:

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- GCC and engagement calculations
- Anomaly and hard-rule decisions
- Identifier-leakage protection
- Model fallback behavior
- Score and report generation
- All Flask routes

The health endpoint is:

```text
GET /health
```

Application logs are written compactly to:

```text
logs/app.log
```

## Sample reports

- [HQ-101-KW Markdown report](outputs/HQ-101-KW.md)
- [HQ-101-KW JSON report](outputs/HQ-101-KW.json)

HQ-101-KW is a representative successful candidate with an `ONBOARD` recommendation and a score of approximately 80.

HQ-109-POD-SUSPECT is useful for demonstrating the anomaly and `MANUAL REVIEW` path.

## Thought process and design decisions

The reasoning behind the feature choices, thresholds, anomaly checks, model split, and deliberate exclusions is documented in:

- [Raw thought process](raw_thought.txt)
- [Implementation plan](Implmentation_plan.md)
- [Implementation steps](implementation_steps.md)
- [Compacting and code minimization guide](compacting.md)

The central design decision is to optimize for Boutique-owner potential rather than vanity reach. GCC relevance, audience trust, commercial behavior, catalog fit, and anomaly protection are prioritized over follower count alone.

## Deliberate cuts

This prototype intentionally does not include:

- Instagram or TikTok scraping
- Paid creator-data APIs
- A trained machine-learning model
- A database
- Multi-agent orchestration
- A frontend framework
- Historical conversion-model training

These were excluded to keep the prototype small, explainable, testable, and defensible within the assessment timeframe.
