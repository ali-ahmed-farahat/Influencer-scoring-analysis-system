# Add Implementation Steps to `Implmentation_plan.md`

## Current state

`Implmentation_plan.md` already contains the architecture, scoring rules, model responsibilities, interface requirements, and acceptance criteria.

Add the following implementation sequence after the Summary section.

## Implementation steps

### Step 1: Prepare the Python project

1. Create the application folders:

```text
templates/
static/
outputs/
tests/
```

2. Create:

```text
main.py
pipeline.py
models.py
app.py
requirements.txt
.env.example
```

3. Add only the required dependencies:

```text
Flask
pydantic
python-dotenv
```

Add provider SDKs only if the selected model adapters require them.

4. Keep `raw_data.json` as the only input dataset.

### Step 2: Create shared data schemas

1. Define Pydantic models for:

- Candidate profile
- Audience insights
- Performance metrics
- Recent content signal
- Derived metrics
- Post-level model output
- Brand-fit output
- Score breakdown
- Final analysis result

2. Validate every candidate before processing.

3. Return clear validation errors for:

- Missing required fields
- Invalid percentages
- Negative follower counts
- Invalid engagement values
- Empty post lists

### Step 3: Implement candidate loading

1. Load `raw_data.json`.
2. Create a function to return all candidates.
3. Create a function to retrieve one candidate by `account_id`.
4. Raise a user-friendly error when the account ID does not exist.
5. Use `HQ-110-HIGH-CONVERSION` as the default demonstration candidate.

### Step 4: Implement deterministic preprocessing

Implement functions for:

```text
calculate_gcc_audience_pct()
calculate_gcc_reachable_audience()
calculate_engagement_rate()
calculate_likes_to_comments_ratio()
calculate_commercial_content_rate()
detect_anomalies()
apply_hard_rules()
```

Use the GCC countries:

```text
Kuwait
Saudi Arabia
United Arab Emirates
Qatar
Bahrain
Oman
```

Apply:

```text
GCC audience < 45% → PASS
Private account → MANUAL REVIEW
anomaly_detected = true → MANUAL REVIEW
```

Do not calculate verified collaboration rate because the current data does not contain sponsorship evidence.

Do not calculate true post volatility because post-level performance data is unavailable.

### Step 5: Implement Qwen extraction

1. Create a Qwen adapter for post-level caption analysis.
2. Send one post at a time.
3. Require structured JSON output.
4. Validate the output with Pydantic.
5. Extract:

```text
commercial_intent_score
has_call_to_action
has_discount_code
has_restock_signal
has_product_review
has_unboxing
has_product_education
sales_framing
evidence
confidence
```

6. Do not use regex in the prototype.
7. If Qwen is unavailable, use the existing `has_commercial_intent` field and clearly mark the result as fallback output.

### Step 6: Implement Gemini brand analysis

1. Create a Gemini adapter for all tagged brands.
2. Classify:

```text
brand_category
prestige_tier
catalog_fit_score
catalog_fit_reason
confidence
```

3. Use the creator category and caption context as additional input.
4. Do not treat a brand tag as proof of sponsorship.
5. If Gemini is unavailable, return an explicitly labelled fallback result.

### Step 7: Aggregate post and brand signals

Aggregate model outputs into candidate-level features:

```text
commercial_intent_rate
average_commercial_intent_score
cta_rate
discount_code_rate
product_review_rate
average_catalog_fit_score
luxury_or_prestige_brand_rate
```

Only calculate verified collaboration rate if explicit sponsorship fields are later added to the dataset.

### Step 8: Implement the weighted scoring engine

Calculate the four scoring dimensions:

```text
Audience commercial viability       30%
Commercialization and intent        25%
Category and brand alignment        25%
Content quality and consistency     20%
```

Produce a transparent score breakdown showing:

- Component score
- Maximum possible points
- Evidence used
- Negative deductions
- Missing or unavailable data

Apply hard rules before the weighted score.

Use:

```text
Score >= 75 → ONBOARD
Score 60–74 → HOLD
Score < 60   → PASS
```

Hard-rule outcomes take priority over score-based outcomes.

### Step 9: Implement the final explanation

1. Prepare a compact evidence object containing:

- Candidate identity
- Derived metrics
- Anomaly flags
- Hard-rule results
- Score breakdown
- Positive signals
- Negative signals
- Model limitations

2. Send this evidence to the larger reasoning model.
3. Ask for:

```text
recommendation_summary
key_positive_signals
key_negative_signals
trade_off_analysis
suggested_next_action
limitations
```

4. The reasoning model may explain the decision but must not change the score or decision.
5. If the reasoning model is unavailable, generate a simple deterministic explanation from templates.

### Step 10: Implement report generation

Generate:

```text
outputs/<account_id>.json
outputs/<account_id>.md
```

The JSON is the machine-readable source for the web interface.

The Markdown report is the human-readable assessment artifact.

Include model status in both outputs:

```text
live
fallback
partial
unavailable
```

### Step 11: Implement the web interface

1. Create the Flask application.
2. Add:

```text
GET /
GET /analyze/<account_id>
GET /health
```

3. On `/`, load all candidates and show a dropdown.
4. On `/analyze/<account_id>`, run the shared pipeline.
5. Render:

- Recommendation banner
- Final score
- Score components
- Key metrics
- Positive signals
- Negative signals
- Anomaly flags
- Suggested action
- Limitations

6. Use plain HTML and CSS.
7. Do not duplicate scoring logic in Flask routes.
8. Do not add a frontend framework or charting library.

### Step 12: Add tests

Test deterministic functions first:

- GCC calculation
- GCC reachable audience
- Engagement rate
- Likes-to-comments ratio
- Zero comments
- Commercial-content rate
- GCC hard rule
- Private-account rule
- Anomaly rule
- Score thresholds

Test representative candidates:

```text
HQ-110-HIGH-CONVERSION → strong onboarding candidate
HQ-102-GL → PASS because GCC audience is below threshold
HQ-109-POD-SUSPECT → MANUAL REVIEW because anomaly is detected
```

Test model fallback behavior:

- Qwen unavailable
- Gemini unavailable
- Final reasoning model unavailable

Test Flask behavior:

- Candidate list loads
- Default candidate appears
- Analysis page renders
- Unknown candidate returns a friendly error
- Health endpoint succeeds

### Step 13: Run the complete demo

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Then:

1. Select a candidate.
2. Run the analysis.
3. Review the recommendation.
4. Verify the score breakdown.
5. Verify the limitations.
6. Confirm JSON and Markdown reports were written.

### Step 14: Final quality check

Before submission:

- Run all tests.
- Run the application from a clean terminal.
- Confirm no API keys are committed.
- Confirm `.env.example` documents required variables.
- Confirm fallback behavior is clearly labelled.
- Confirm the final model cannot override deterministic decisions.
- Confirm the README explains the architecture, limitations, and deliberate exclusions.
- Confirm the prototype remains limited to one candidate per run and the 10-record mock dataset.

## Definition of done

The implementation is complete when a non-technical user can open the browser interface, select one of the candidates, receive an explainable recommendation, and view the supporting metrics without reading or running Python code.
